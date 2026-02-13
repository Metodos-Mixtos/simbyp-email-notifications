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
    Endpoint to send weekly alerts (deforestation + land cover).
    Triggered by Cloud Scheduler every Tuesday.
    Skips if no alerts found.
    """
    try:
        logger.info("Starting weekly alerts generation")
        
        # Get weekly alerts (deforestation + land_cover)
        alerts = alert_processor.get_weekly_alerts()
        total_alerts = sum(len(v) for v in alerts.values())
        
        if total_alerts == 0:
            logger.info("No weekly alerts to send")
            return jsonify({
                'status': 'skipped',
                'message': 'No alerts found for this week',
                'alerts': total_alerts
            }), 204
        
        # Get recipients
        recipients = RECIPIENTS.get('weekly_alerts_recipients', [])
        
        if not recipients:
            logger.warning("No recipients configured for weekly alerts")
            return jsonify({
                'status': 'warning',
                'message': 'No recipients configured'
            }), 200
        
        # Check for duplicates
        # Create a composite key from alerts
        alert_key = f"weekly_alerts_{','.join(sorted([a['report_name'] for alerts_list in alerts.values() for a in alerts_list]))}"
        if utils.is_alert_already_sent('weekly_alerts', alert_key, recipients):
            logger.warning(f"Weekly alerts already sent to these recipients")
            return jsonify({
                'status': 'skipped',
                'message': 'Alerts already sent to these recipients this week'
            }), 204
        
        # Send email
        success = email_service.send_weekly_alerts(recipients, alerts)
        
        if success:
            # Record the sent alert
            utils.record_sent_alert('weekly_alerts', alert_key, recipients)
            return jsonify({
                'status': 'success',
                'message': 'Weekly alerts sent successfully',
                'alerts': total_alerts,
                'recipients': recipients
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send weekly alerts'
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
        logger.info("Checking if today is first Friday of month for built area report")
        
        # Check if today is the first Friday
        if not utils.is_first_friday_of_month():
            logger.info(f"Today is not the first Friday of the month; skipping")
            return jsonify({
                'status': 'skipped',
                'message': 'Not the first Friday of the month'
            }), 204
        
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
        
        # Create a composite alert data
        alert_data = {
            'alerts': alerts,
            'count': len(alerts),
            'title': 'Reporte Mensual de Área Construida'
        }
        
        # Check for duplicates
        alert_key = f"monthly_built_area_{','.join(sorted([a['report_name'] for a in alerts]))}"
        if utils.is_alert_already_sent('monthly_built_area', alert_key, recipients):
            logger.warning(f"Monthly built area report already sent to these recipients")
            return jsonify({
                'status': 'skipped',
                'message': 'Report already sent to these recipients this month'
            }), 204
        
        # Send email
        success = email_service.send_monthly_built_area(recipients, alert_data)
        
        if success:
            # Record the sent alert
            utils.record_sent_alert('monthly_built_area', alert_key, recipients)
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
    """Test endpoint to see what alerts would be sent"""
    try:
        weekly_alerts = alert_processor.get_weekly_alerts()
        monthly_alerts = alert_processor.get_monthly_built_area()
        is_first_friday = utils.is_first_friday_of_month()
        
        return jsonify({
            'weekly_alerts': {
                'deforestation': [{'title': a['title'], 'updated': a['updated'].isoformat()} for a in weekly_alerts.get('deforestation', [])],
                'land_cover': [{'title': a['title'], 'updated': a['updated'].isoformat()} for a in weekly_alerts.get('land_cover', [])]
            },
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