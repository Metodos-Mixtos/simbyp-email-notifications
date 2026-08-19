# Configure logging FIRST - before importing config module
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Now import config and other modules
from flask import Flask, request, jsonify, render_template
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

app = Flask(__name__, static_folder='src/static', static_url_path='/static', template_folder='src/templates')
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
    return render_template('admin.html')

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


@app.route('/api/batch-import-template', methods=['GET'])
def get_batch_import_template():
    """Download CSV template for batch user import"""
    from src.config import DB_ENABLED
    
    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503
    
    try:
        from src.database import get_db_session
        from src.services.batch_import_service import BatchImportService
        
        with get_db_session() as session:
            import_service = BatchImportService(session)
            csv_content = import_service.generate_template_csv()
        
        # Return CSV file for download
        return csv_content, 200, {
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename=plantilla_correos_template.csv'
        }
    
    except Exception as e:
        logger.error(f"Error generating template: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/batch-import', methods=['POST'])
def batch_import_users():
    """Batch import users and subscriptions from CSV file"""
    from src.config import DB_ENABLED
    
    if not DB_ENABLED:
        return jsonify({'success': False, 'error': 'Database not enabled'}), 503
    
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        csv_file = request.files['file']
        
        if csv_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Validate file type
        if not csv_file.filename.endswith('.csv'):
            return jsonify({'success': False, 'error': 'File must be a CSV file'}), 400
        
        # Check file size (max 10MB)
        csv_file.seek(0, 2)  # Seek to end
        file_size = csv_file.tell()
        csv_file.seek(0)  # Reset to beginning
        
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            return jsonify({'success': False, 'error': 'File too large (max 10MB)'}), 413
        
        # Performed by is always 'admin' for now (no user session management)
        performed_by = 'admin'
        
        from src.database import get_db_session
        from src.services.batch_import_service import BatchImportService
        
        with get_db_session() as db_session:
            import_service = BatchImportService(db_session)
            result = import_service.import_users_batch(csv_file, performed_by)
        
        return jsonify(result.to_dict()), 200
    
    except Exception as e:
        logger.error(f"Error in batch import: {e}", exc_info=True)
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


# ========================================================================
# Paramos Reports Endpoints
# ========================================================================

@app.route('/api/reports/paramos/sync', methods=['POST'])
def sync_paramos_report():
    """
    Trigger synchronization of a paramos report from Dynamic World.
    
    Query Parameters:
        year (int): Year of report (e.g., 2026) - defaults to current year
        month (int): Month of report (1-12) - defaults to current month
        token (str): Authentication token (optional for webhook)
    
    Returns:
        {
            'success': bool,
            'data': {
                'report_id': str,
                'title': str,
                'url': str,
                'recipients': int
            },
            'error': str (on failure)
        }
    """
    try:
        # Get year and month from request
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        # If not provided, use current date
        if not year or not month:
            from datetime import datetime
            today = datetime.today()
            year = year or today.year
            month = month or today.month
        
        # Validate year and month
        if not (1900 <= year <= 2100) or not (1 <= month <= 12):
            return jsonify({
                'success': False,
                'error': 'Invalid year or month. Year must be 1900-2100, month 1-12'
            }), 400
        
        from src.database import get_db_session
        from src.services.paramos_monitor_service import ParamosMonitorService
        
        with get_db_session() as session:
            paramos_service = ParamosMonitorService(session)
            success, report_id = paramos_service.sync_paramos_report(year, month)
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': f'No new paramos report found for {year}-{month:02d}'
                }), 404
            
            # Get report details
            report = paramos_service.report_repo.get_report_by_id(UUID(report_id))
            
            return jsonify({
                'success': True,
                'data': {
                    'report_id': report_id,
                    'title': report.report_title,
                    'url': report.report_url,
                    'recipients': report.recipient_count
                }
            }), 200
    
    except Exception as e:
        logger.error(f"Error syncing paramos report: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/reports/paramos/latest', methods=['GET'])
def get_latest_paramos_report():
    """
    Get metadata for the latest paramos report.
    
    Returns:
        {
            'success': bool,
            'data': {
                'id': str,
                'title': str,
                'url': str,
                'sent_at': str (ISO format),
                'recipient_count': int,
                'status': str
            },
            'error': str (on failure)
        }
    """
    try:
        from src.database import get_db_session
        from src.services.paramos_monitor_service import ParamosMonitorService
        
        with get_db_session() as session:
            paramos_service = ParamosMonitorService(session)
            report_data = paramos_service.get_latest_report()
            
            if not report_data:
                return jsonify({
                    'success': False,
                    'error': 'No paramos reports found'
                }), 404
            
            return jsonify({
                'success': True,
                'data': report_data
            }), 200
    
    except Exception as e:
        logger.error(f"Error getting latest paramos report: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)