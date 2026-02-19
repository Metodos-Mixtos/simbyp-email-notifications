from flask import Flask, request, jsonify
import logging
from src.config import GCP_PROJECT_ID, RECIPIENTS, PORT
from src.gcs_handler import GCSHandler
from src.alerts_processor import AlertProcessor
from src.email_service import EmailService
from src import utils

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize services
gcs_handler = GCSHandler(GCP_PROJECT_ID)
alert_processor = AlertProcessor(gcs_handler)
email_service = EmailService()

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'simbyp-email-notifications'}), 200

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
        
        # Get latest weekly alerts report
        weekly_report = alert_processor.get_latest_weekly_alerts_report()
        
        if not weekly_report:
            logger.info("No weekly report found to send")
            return jsonify({
                'status': 'skipped',
                'message': 'No weekly report found',
                'report': None
            }), 204
        
        # Get recipients
        recipients = RECIPIENTS.get('weekly_alerts_recipients', [])
        
        if not recipients:
            logger.warning("No recipients configured for weekly alerts")
            return jsonify({
                'status': 'warning',
                'message': 'No recipients configured'
            }), 200
        
        # Send email with report only
        success = email_service.send_weekly_report(recipients, weekly_report)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Weekly report sent successfully',
                'report': weekly_report['title'],
                'recipients': recipients
            }), 200
        else:
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
        logger.info("Starting built area report generation")
        
        # Get built area alerts
        alerts = alert_processor.get_monthly_built_area()
        
        if not alerts:
            logger.info("No built area alerts to send")
            return jsonify({
                'status': 'skipped',
                'message': 'No built area alerts found',
                'alerts': 0
            }), 204
        
        # Get recipients
        recipients = RECIPIENTS.get('monthly_built_area_recipients', [])
        
        if not recipients:
            logger.warning("No recipients configured for monthly built area")
            return jsonify({
                'status': 'warning',
                'message': 'No recipients configured'
            }), 200
        
        # Get the first (and only) alert
        alert_data = alerts[0]
        
        # Send email
        success = email_service.send_monthly_built_area(recipients, alert_data)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Monthly built area report sent successfully',
                'alerts': len(alerts),
                'recipients': recipients
            }), 200
        else:
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)