"""
Enhanced Notification Service for Grocery AI

Handles email, SMS, push notifications, and in-app notifications
for automated alerts and user communications.
"""

import smtplib
import json
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
from jinja2 import Template

from src.core.config import Config
from src.data.models import get_session, User, Notification

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.email_enabled = bool(Config.SMTP_HOST and Config.SMTP_USER and Config.SMTP_PASSWORD)
        self.sms_enabled = False  # Can be enabled with Twilio/similar service
        
        if self.email_enabled:
            logger.info("📧 Email notifications enabled")
        else:
            logger.info("📧 Email notifications disabled - configure SMTP settings to enable")
    
    async def send_notification(
        self, 
        user_id: int, 
        type: str, 
        title: str, 
        message: str, 
        data: Dict[str, Any] = None,
        channels: List[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification to user via multiple channels
        
        Args:
            user_id: User to notify
            type: Notification type (meal_plan_created, low_stock_alert, etc.)
            title: Notification title
            message: Notification message
            data: Additional data for the notification
            channels: Channels to send to ['email', 'sms', 'push', 'in_app']
        """
        
        if channels is None:
            channels = ['in_app']  # Default to in-app notifications
        
        if data is None:
            data = {}
        
        try:
            # Store in-app notification
            notification_id = await self._store_notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                data=data
            )
            
            # Get user details
            session = get_session()
            user = session.query(User).filter(User.id == user_id).first()
            session.close()
            
            if not user:
                logger.error(f"User {user_id} not found for notification")
                return {"success": False, "error": "User not found"}
            
            results = {"in_app": True}
            
            # Send via requested channels
            if 'email' in channels and self.email_enabled and user.email:
                email_result = await self._send_email_notification(
                    user=user,
                    type=type,
                    title=title,
                    message=message,
                    data=data
                )
                results['email'] = email_result
            
            if 'sms' in channels and self.sms_enabled:
                sms_result = await self._send_sms_notification(
                    user=user,
                    type=type,
                    title=title,
                    message=message,
                    data=data
                )
                results['sms'] = sms_result
            
            if 'push' in channels:
                # Push notifications would be implemented here
                results['push'] = False  # Not implemented yet
            
            logger.info(f"📬 Sent notification to user {user_id}: {title}")
            
            return {
                "success": True,
                "notification_id": notification_id,
                "channels": results
            }
            
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _store_notification(
        self, 
        user_id: int, 
        type: str, 
        title: str, 
        message: str, 
        data: Dict[str, Any]
    ) -> int:
        """Store notification in database"""
        
        try:
            session = get_session()
            
            notification = Notification(
                user_id=user_id,
                type=type,
                title=title,
                message=message,
                data=json.dumps(data) if data else None,
                is_read=False,
                created_at=datetime.now()
            )
            
            session.add(notification)
            session.commit()
            notification_id = notification.id
            session.close()
            
            return notification_id
            
        except Exception as e:
            logger.error(f"Failed to store notification: {e}")
            raise
    
    async def _send_email_notification(
        self, 
        user: User, 
        type: str, 
        title: str, 
        message: str, 
        data: Dict[str, Any]
    ) -> bool:
        """Send email notification"""
        
        try:
            # Get email template
            email_content = self._get_email_template(type, title, message, data, user)
            
            # Create email
            msg = MimeMultipart('alternative')
            msg['Subject'] = f"🍎 Grocery AI - {title}"
            msg['From'] = Config.SMTP_USER
            msg['To'] = user.email
            
            # Add HTML content
            html_part = MimeText(email_content['html'], 'html')
            text_part = MimeText(email_content['text'], 'plain')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"📧 Email sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {user.email}: {e}")
            return False
    
    async def _send_sms_notification(
        self, 
        user: User, 
        type: str, 
        title: str, 
        message: str, 
        data: Dict[str, Any]
    ) -> bool:
        """Send SMS notification (placeholder - implement with Twilio)"""
        
        # This would integrate with Twilio or similar SMS service
        logger.info(f"📱 SMS notification would be sent to user {user.id}: {title}")
        return False  # Not implemented yet
    
    def _get_email_template(
        self, 
        type: str, 
        title: str, 
        message: str, 
        data: Dict[str, Any], 
        user: User
    ) -> Dict[str, str]:
        """Get formatted email template"""
        
        # Base HTML template
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }
                .button { background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; margin: 10px 0; }
                .footer { text-align: center; color: #666; font-size: 12px; margin-top: 20px; }
                .highlight { background: #e3f2fd; padding: 15px; border-radius: 6px; margin: 15px 0; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🍎 Grocery AI</h1>
                <h2>{{ title }}</h2>
            </div>
            <div class="content">
                <p>Hi {{ user_name }},</p>
                <p>{{ message }}</p>
                
                {% if type == 'meal_plan_created' %}
                    <div class="highlight">
                        <h3>Your New Meal Plan</h3>
                        <p>We've created a personalized meal plan based on your preferences and budget.</p>
                        <a href="{{ app_url }}/meals" class="button">View Meal Plan</a>
                    </div>
                {% elif type == 'low_stock_alert' %}
                    <div class="highlight">
                        <h3>Items Running Low</h3>
                        {% if low_stock_items %}
                            <ul>
                            {% for item in low_stock_items[:5] %}
                                <li>{{ item.name }} ({{ item.quantity }} {{ item.unit }} remaining)</li>
                            {% endfor %}
                            </ul>
                        {% endif %}
                        <a href="{{ app_url }}/inventory" class="button">Check Inventory</a>
                    </div>
                {% elif type == 'price_alert' %}
                    <div class="highlight">
                        <h3>Great Deals Found!</h3>
                        {% if deals %}
                            <p>We found {{ deals|length }} great deals for items you buy regularly:</p>
                            <ul>
                            {% for deal in deals[:3] %}
                                <li>{{ deal.product_name }} - Save ${{ "%.2f"|format(deal.savings) }} ({{ deal.discount_percent }}% off)</li>
                            {% endfor %}
                            </ul>
                        {% endif %}
                        <a href="{{ app_url }}/shopping" class="button">View Deals</a>
                    </div>
                {% endif %}
                
                <p>Best regards,<br>Your Grocery AI Assistant</p>
            </div>
            <div class="footer">
                <p>This is an automated message from Grocery AI. You can manage your notification preferences in your profile.</p>
            </div>
        </body>
        </html>
        """)
        
        # Text template
        text_template = Template("""
        Grocery AI - {{ title }}
        
        Hi {{ user_name }},
        
        {{ message }}
        
        {% if type == 'meal_plan_created' %}
        Your new meal plan is ready! Visit {{ app_url }}/meals to view it.
        {% elif type == 'low_stock_alert' %}
        Items running low:
        {% if low_stock_items %}
        {% for item in low_stock_items[:5] %}
        - {{ item.name }} ({{ item.quantity }} {{ item.unit }} remaining)
        {% endfor %}
        {% endif %}
        
        Check your inventory: {{ app_url }}/inventory
        {% elif type == 'price_alert' %}
        Great deals found:
        {% if deals %}
        {% for deal in deals[:3] %}
        - {{ deal.product_name }} - Save ${{ "%.2f"|format(deal.savings) }}
        {% endfor %}
        {% endif %}
        
        View deals: {{ app_url }}/shopping
        {% endif %}
        
        Best regards,
        Your Grocery AI Assistant
        
        ---
        This is an automated message from Grocery AI.
        """)
        
        # Template variables
        template_vars = {
            'title': title,
            'message': message,
            'user_name': user.name,
            'type': type,
            'app_url': Config.APP_URL or 'http://localhost:3000',
            'low_stock_items': data.get('low_stock_items', []),
            'deals': data.get('deals', [])
        }
        
        return {
            'html': html_template.render(**template_vars),
            'text': text_template.render(**template_vars)
        }
    
    async def get_user_notifications(
        self, 
        user_id: int, 
        limit: int = 20, 
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get user notifications"""
        
        try:
            session = get_session()
            
            query = session.query(Notification).filter(Notification.user_id == user_id)
            
            if unread_only:
                query = query.filter(Notification.is_read == False)
            
            notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
            
            result = []
            for notif in notifications:
                result.append({
                    'id': notif.id,
                    'type': notif.type,
                    'title': notif.title,
                    'message': notif.message,
                    'data': json.loads(notif.data) if notif.data else {},
                    'is_read': notif.is_read,
                    'created_at': notif.created_at.isoformat()
                })
            
            session.close()
            return result
            
        except Exception as e:
            logger.error(f"Failed to get notifications for user {user_id}: {e}")
            return []
    
    async def mark_notification_read(self, notification_id: int, user_id: int) -> bool:
        """Mark notification as read"""
        
        try:
            session = get_session()
            
            notification = session.query(Notification).filter(
                Notification.id == notification_id,
                Notification.user_id == user_id
            ).first()
            
            if notification:
                notification.is_read = True
                session.commit()
                session.close()
                return True
            
            session.close()
            return False
            
        except Exception as e:
            logger.error(f"Failed to mark notification {notification_id} as read: {e}")
            return False

# Global notification service instance
notification_service = NotificationService()