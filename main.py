# Configure logging FIRST - before importing config module
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Now import config and other modules
from flask import Flask, request, jsonify
from src.config import (
    GCP_PROJECT_ID, PORT, 
    AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET, 
    FROM_EMAIL, FROM_NAME,
    DATABASE_URL
)
from src.gcs_handler import GCSHandler
from src.alerts_processor import AlertProcessor
from src.email_service import EmailService
from src import utils

app = Flask(__name__, static_folder='src/static', static_url_path='/static')
app.config['JSON_SORT_KEYS'] = False


def _report_to_email_payload(report) -> dict:
    """Convert ORM report row to email payload dict expected by EmailService."""
    if not report:
        return {}

    return {
        'id': str(report.id),
        'alert_type': report.alert_type,
        'report_title': report.report_title,
        'report_url': report.report_url,
        'report_date': report.report_date.isoformat() if report.report_date else None,
        'sent_at': report.sent_at.isoformat() if report.sent_at else None,
        'metadata': report.metadata_json or {},
    }


def _extract_metadata_files(metadata: dict) -> list:
    """Extract file list candidates from known metadata keys for preview responses."""
    if not isinstance(metadata, dict):
        return []

    files = []
    for key in ('files', 'report_files', 'file_links', 'email_files'):
        value = metadata.get(key)
        if isinstance(value, list):
            files.extend(value)
    return files


def _serialize_report_candidate(report) -> dict:
    """Serialize report candidate row for admin/debug queue preview."""
    metadata = report.metadata_json or {}
    files = _extract_metadata_files(metadata)
    return {
        'id': str(report.id),
        'alert_type': report.alert_type,
        'report_title': report.report_title,
        'report_url': report.report_url,
        'report_date': report.report_date.isoformat() if report.report_date else None,
        'sent_at': report.sent_at.isoformat() if report.sent_at else None,
        'status': report.status,
        'files_count': len(files),
        'files': files,
        'metadata': metadata,
    }

# Database is required - initialize connection
if not DATABASE_URL:
    logger.error("DATABASE_URL is not configured")
    raise RuntimeError(
        "DATABASE_URL is required. The application now requires a PostgreSQL database. "
        "Please set DATABASE_URL environment variable. "
        "See docs/CLOUD_SQL_SETUP.md for setup instructions."
    )

logger.info("Initializing database connection...")
from src.database import init_db
init_db(DATABASE_URL, pool_size=5, max_overflow=10)
logger.info("✓ Database initialized successfully")

# Initialize services
gcs_handler = GCSHandler(GCP_PROJECT_ID)
alert_processor = AlertProcessor(gcs_handler)
email_service = EmailService(
    client_id=AZURE_CLIENT_ID,
    tenant_id=AZURE_TENANT_ID,
    client_secret=AZURE_CLIENT_SECRET,
    from_email=FROM_EMAIL,
    from_name=FROM_NAME
)

@app.route('/')
def health_check():
    """Health check endpoint"""
    health_status = {
        'status': 'healthy',
        'service': 'simbyp-email-notifications',
        'database': {
            'enabled': True
        }
    }
    
    try:
        from src.database import check_db_health
        db_healthy, db_message = check_db_health()
        health_status['database']['status'] = 'healthy' if db_healthy else 'unhealthy'
        health_status['database']['message'] = db_message
    except Exception as e:
        health_status['database']['status'] = 'error'
        health_status['database']['message'] = str(e)
    
    return jsonify(health_status), 200

@app.route('/health/db', methods=['GET'])
def database_health():
    """Database health check endpoint"""
    try:
        from src.database import check_db_health
        is_healthy, message = check_db_health()
        
        if is_healthy:
            return jsonify({
                'status': 'healthy',
                'message': message
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'message': message
            }), 503
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/send-weekly-alerts', methods=['POST'])
def send_weekly_alerts():
    """
    Endpoint to send the latest weekly alerts report.
    Fetches and sends the most recent weekly report.
    Triggered by Cloud Scheduler every Tuesday.
    Skips if no report found.
    """
    try:
        logger.info("Starting weekly alerts report sending")

        # Get report candidate and recipients from database
        from src.database import get_db_session
        from src.repositories.subscription_repository import SubscriptionRepository
        from src.repositories.report_repository import ReportRepository
        
        with get_db_session() as session:
            report_repo = ReportRepository(session)
            sub_repo = SubscriptionRepository(session)

            weekly_report_row = report_repo.get_next_generated_report('weekly_alerts')
            if not weekly_report_row:
                logger.info("No generated weekly report found to send")
                return jsonify({
                    'status': 'skipped',
                    'message': 'No generated weekly report found',
                    'report': None
                }), 200

            recipients = sub_repo.get_recipients_by_alert_type('weekly_alerts')

            if not recipients:
                logger.warning("No recipients configured for weekly alerts")
                return jsonify({
                    'status': 'warning',
                    'message': 'No recipients configured'
                }), 200

            weekly_report = _report_to_email_payload(weekly_report_row)

            # Send email with report only
            success = email_service.send_weekly_report(recipients, weekly_report)

            if success:
                report_repo.update_report_status(
                    weekly_report_row.id,
                    status='sent',
                    recipient_count=len(recipients),
                    error_message=None
                )
                return jsonify({
                    'status': 'success',
                    'message': 'Weekly report sent successfully',
                    'report': weekly_report_row.report_title,
                    'recipients': recipients
                }), 200

            report_repo.update_report_status(
                weekly_report_row.id,
                status='failed',
                recipient_count=0,
                error_message='Failed to send weekly report email via Microsoft Graph API'
            )
            return jsonify({
                'status': 'error',
                'message': 'Failed to send weekly report'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in send_weekly_alerts: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/send-monthly-built-area', methods=['POST'])
def send_monthly_built_area():
    """
    Endpoint to send monthly built area report.
    Triggered by Cloud Scheduler daily, but only sends on first Friday of month.
    Skips if no alerts found.
    """
    try:
        logger.info("Starting monthly built area report sending")

        # Get report candidate and recipients from database
        from src.database import get_db_session
        from src.repositories.subscription_repository import SubscriptionRepository
        from src.repositories.report_repository import ReportRepository
        
        with get_db_session() as session:
            report_repo = ReportRepository(session)
            sub_repo = SubscriptionRepository(session)

            monthly_report_row = report_repo.get_next_generated_report('monthly_built_area')
            if not monthly_report_row:
                logger.info("No generated monthly built area report found to send")
                return jsonify({
                    'status': 'skipped',
                    'message': 'No generated monthly built area report found',
                    'alerts': 0
                }), 200

            recipients = sub_repo.get_recipients_by_alert_type('monthly_built_area')

            if not recipients:
                logger.warning("No recipients configured for monthly built area")
                return jsonify({
                    'status': 'warning',
                    'message': 'No recipients configured'
                }), 200

            alert_data = _report_to_email_payload(monthly_report_row)

            # Send email
            success = email_service.send_monthly_built_area(recipients, alert_data)

            if success:
                report_repo.update_report_status(
                    monthly_report_row.id,
                    status='sent',
                    recipient_count=len(recipients),
                    error_message=None
                )
                return jsonify({
                    'status': 'success',
                    'message': 'Monthly built area report sent successfully',
                    'alerts': 1,
                    'recipients': recipients
                }), 200

            report_repo.update_report_status(
                monthly_report_row.id,
                status='failed',
                recipient_count=0,
                error_message='Failed to send monthly built area report email via Microsoft Graph API'
            )
            return jsonify({
                'status': 'error',
                'message': 'Failed to send monthly built area report'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in send_monthly_built_area: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/test-alerts', methods=['GET'])
def test_alerts():
    """Test endpoint to see what would be sent"""
    try:
        weekly_report = alert_processor.get_latest_weekly_alerts_report()
        monthly_alerts = alert_processor.get_monthly_built_area()
        is_first_friday = utils.is_first_friday_of_month()
        
        return jsonify({
            'weekly_report': {
                'title': weekly_report['title'] if weekly_report else None,
                'url': weekly_report['url'] if weekly_report else None,
                'start_date': weekly_report['start_date'] if weekly_report else None,
                'end_date': weekly_report['end_date'] if weekly_report else None,
                'updated': weekly_report['updated'].isoformat() if weekly_report else None
            } if weekly_report else None,
            'monthly_built_area': {
                'alerts': [{'title': a['title'], 'updated': a['updated'].isoformat()} for a in monthly_alerts],
                'is_first_friday': is_first_friday
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error in test_alerts: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN USER MANAGEMENT API
# ============================================================================

@app.route('/admin')
def admin_interface():
    """Admin interface for user management"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>User Management - SIMBYP Email Notifications</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .loading { display: none; }
            .loading.show { display: inline-block; }
            .toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; }
            .subscription-badge { margin: 2px; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-primary">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">SIMBYP User Management</span>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="row mb-3">
                <div class="col">
                    <h2>Email Recipients</h2>
                </div>
                <div class="col text-end">
                    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#userModal" onclick="resetUserForm()">
                        <i class="bi bi-plus-circle"></i> Add User
                    </button>
                </div>
            </div>
            
            <div class="card">
                <div class="card-body">
                    <div class="mb-3">
                        <input type="text" id="searchInput" class="form-control" placeholder="Search by email or name...">
                    </div>
                    
                    <div id="loadingSpinner" class="text-center py-4">
                        <div class="spinner-border" role="status"></div>
                    </div>
                    
                    <div id="userTableContainer" style="display: none;">
                        <table class="table table-striped table-hover">
                            <thead>
                                <tr>
                                    <th>Email</th>
                                    <th>Name</th>
                                    <th>Department</th>
                                    <th>Municipality</th>
                                    <th>Subscriptions</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="userTableBody"></tbody>
                        </table>
                    </div>
                    
                    <div id="emptyState" class="text-center py-4" style="display: none;">
                        <p class="text-muted">No users found. Click "Add User" to create one.</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- User Modal -->
        <div class="modal fade" id="userModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="modalTitle">Add User</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="userForm">
                            <input type="hidden" id="userId">
                            <div class="mb-3">
                                <label for="userEmail" class="form-label">Email *</label>
                                <input type="email" class="form-control" id="userEmail" required>
                            </div>
                            <div class="mb-3">
                                <label for="userName" class="form-label">Name</label>
                                <input type="text" class="form-control" id="userName">
                            </div>
                            <div class="mb-3">
                                <label for="userDepartment" class="form-label">Department</label>
                                <input type="text" class="form-control" id="userDepartment">
                            </div>
                            <div class="mb-3">
                                <label for="userMunicipality" class="form-label">Municipality Code</label>
                                <input type="text" class="form-control" id="userMunicipality" placeholder="e.g., 11001">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Subscriptions</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="subWeekly" value="weekly_alerts">
                                    <label class="form-check-label" for="subWeekly">Weekly Alerts (Deforestation + Land Cover)</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="subMonthly" value="monthly_built_area">
                                    <label class="form-check-label" for="subMonthly">Monthly Built Area</label>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="saveUserButton" onclick="saveUser(event)">
                            <span class="spinner-border spinner-border-sm loading" role="status"></span>
                            Save
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Toast Container -->
        <div class="toast-container"></div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="/static/js/admin.js"></script>
    </body>
    </html>
    """

@app.route('/api/users', methods=['GET'])
def list_users():
    """List all users with pagination"""
    try:
        from src.database import get_db_session
        from src.repositories.user_repository import UserRepository
        
        offset = request.args.get('offset', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        with get_db_session() as session:
            user_repo = UserRepository(session)
            users = user_repo.list_all(offset=offset, limit=limit)
            total = user_repo.count()
            
            users_data = []
            for user in users:
                user_dict = user.to_dict()
                user_dict['subscriptions'] = user.get_active_subscription_types()
                users_data.append(user_dict)
            
            return jsonify({
                'success': True,
                'data': users_data,
                'total': total,
                'offset': offset,
                'limit': limit
            }), 200
    
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user"""
    from src.config import DB_ENABLED
    
    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503
    
    try:
        from src.database import get_db_session
        from src.repositories.user_repository import UserRepository
        from src.repositories.subscription_repository import SubscriptionRepository
        
        data = request.get_json()
        
        if not data or not data.get('email'):
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        with get_db_session() as session:
            user_repo = UserRepository(session)
            sub_repo = SubscriptionRepository(session)
            
            # Create user
            user = user_repo.create(
                email=data['email'],
                name=data.get('name'),
                department=data.get('department'),
                municipality_code=data.get('municipality_code')
            )
            
            # Handle subscriptions
            subscriptions = data.get('subscriptions', [])
            for alert_type in subscriptions:
                if alert_type in ['weekly_alerts', 'monthly_built_area']:
                    sub_repo.subscribe(user.id, alert_type, performed_by='admin_ui')
            
            session.commit()
            
            user_dict = user.to_dict()
            user_dict['subscriptions'] = user.get_active_subscription_types()
            
            return jsonify({
                'success': True,
                'data': user_dict,
                'message': 'User created successfully'
            }), 201
    
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user"""
    from src.config import DB_ENABLED
    
    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503
    
    try:
        from uuid import UUID
        from src.database import get_db_session
        from src.repositories.user_repository import UserRepository
        
        user_uuid = UUID(user_id)
        
        with get_db_session() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_with_subscriptions(user_uuid)
            
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            user_dict = user.to_dict()
            user_dict['subscriptions'] = user.get_active_subscription_types()
            
            return jsonify({'success': True, 'data': user_dict}), 200
    
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400
    except Exception as e:
        logger.error(f"Error getting user: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a user"""
    from src.config import DB_ENABLED
    
    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503
    
    try:
        from uuid import UUID
        from src.database import get_db_session
        from src.repositories.user_repository import UserRepository
        from src.repositories.subscription_repository import SubscriptionRepository
        
        user_uuid = UUID(user_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        with get_db_session() as session:
            user_repo = UserRepository(session)
            sub_repo = SubscriptionRepository(session)
            
            # Update user fields
            update_fields = {k: v for k, v in data.items() 
                           if k in ['email', 'name', 'department', 'municipality_code']}
            
            user = user_repo.update(user_uuid, **update_fields)
            
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Handle subscriptions if provided
            if 'subscriptions' in data:
                new_subscriptions = set(data['subscriptions'])
                current_subscriptions = set(user.get_active_subscription_types())
                
                # Subscribe to new ones
                for alert_type in new_subscriptions - current_subscriptions:
                    if alert_type in ['weekly_alerts', 'monthly_built_area']:
                        sub_repo.subscribe(user.id, alert_type, performed_by='admin_ui')
                
                # Unsubscribe from removed ones
                for alert_type in current_subscriptions - new_subscriptions:
                    sub_repo.unsubscribe(user.id, alert_type, performed_by='admin_ui')
            
            session.commit()
            
            # Refresh user to get updated subscriptions
            session.refresh(user)
            user_dict = user.to_dict()
            user_dict['subscriptions'] = user.get_active_subscription_types()
            
            return jsonify({
                'success': True,
                'data': user_dict,
                'message': 'User updated successfully'
            }), 200
    
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating user: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user"""
    from src.config import DB_ENABLED
    
    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503
    
    try:
        from uuid import UUID
        from src.database import get_db_session
        from src.repositories.user_repository import UserRepository
        
        user_uuid = UUID(user_id)
        
        with get_db_session() as session:
            user_repo = UserRepository(session)
            deleted = user_repo.delete(user_uuid)
            
            if not deleted:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            session.commit()
            
            return jsonify({
                'success': True,
                'message': 'User deleted successfully'
            }), 200
    
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid user ID format'}), 400
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/report-queue/next', methods=['GET'])
def get_next_report_candidates():
    """Preview next generated report candidates from reports_sent."""
    from src.config import DB_ENABLED

    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503

    try:
        from src.database import get_db_session
        from src.repositories.report_repository import ReportRepository

        requested_type = request.args.get('alert_type', type=str)
        allowed_types = {'weekly_alerts', 'monthly_built_area'}

        if requested_type and requested_type not in allowed_types:
            return jsonify({
                'success': False,
                'error': 'Invalid alert_type. Use weekly_alerts or monthly_built_area'
            }), 400

        query_types = [requested_type] if requested_type else ['weekly_alerts', 'monthly_built_area']

        with get_db_session() as session:
            report_repo = ReportRepository(session)
            candidates = {}

            for alert_type in query_types:
                report = report_repo.get_next_generated_report(alert_type)
                candidates[alert_type] = _serialize_report_candidate(report) if report else None

        return jsonify({
            'success': True,
            'data': candidates
        }), 200

    except Exception as e:
        logger.error(f"Error getting next report candidates: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)