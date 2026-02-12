from flask import Flask, request, jsonify
import logging
from src.config import GCP_PROJECT_ID, RECIPIENTS, PORT
from src.gcs_handler import GCSHandler
from src.alerts_processor import AlertProcessor
from src.email_service import EmailService

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

@app.route('/send-weekly-digest', methods=['POST'])
def send_weekly_digest():
    """
    Endpoint to send weekly digest.
    Triggered by Cloud Scheduler.
    """
    try:
        logger.info("Starting weekly digest generation")
        
        # Get all pending alerts
        alerts = alert_processor.get_all_pending_alerts()
        summary = alert_processor.get_summary_stats(alerts)
        
        logger.info(f"Summary: {summary}")
        
        # Get recipients
        recipients = RECIPIENTS.get('weekly_digest', [])
        
        if not recipients:
            logger.warning("No recipients configured for weekly digest")
            return jsonify({
                'status': 'warning',
                'message': 'No recipients configured'
            }), 200
        
        # Send email
        success = email_service.send_weekly_digest(recipients, alerts, summary)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Weekly digest sent successfully',
                'summary': summary,
                'recipients': recipients
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send weekly digest'
            }), 500
    
    except Exception as e:
        logger.error(f"Error in send_weekly_digest: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/test-alerts', methods=['GET'])
def test_alerts():
    """Test endpoint to see what alerts would be sent"""
    try:
        alerts = alert_processor.get_all_pending_alerts()
        summary = alert_processor.get_summary_stats(alerts)
        
        return jsonify({
            'summary': summary,
            'alerts': {
                'gfw': [{'title': a['title'], 'updated': a['updated'].isoformat()} for a in alerts.get('gfw', [])],
                'psa': [{'title': a['title'], 'updated': a['updated'].isoformat()} for a in alerts.get('psa', [])],
                'area_construida': [{'title': a['title'], 'updated': a['updated'].isoformat()} for a in alerts.get('area_construida', [])]
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error in test_alerts: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)