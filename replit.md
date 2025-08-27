# Brazilian Military CAC Registration Platform

## Project Overview
A comprehensive web platform for Brazilian military document registration, specifically for CAC (Collectors, Sports Shooters, and Hunters). The platform streamlines administrative processes with a focus on user-friendly digital documentation.

## Architecture

### Backend
- **Flask** - Python web framework
- **SQLAlchemy** - Database ORM
- **PostgreSQL** - Production database (SQLite for development)
- **Gunicorn** - WSGI server for production

### Frontend
- **Tailwind CSS** - Utility-first CSS framework
- **Font Awesome** - Icon library
- **Rawline Font** - Custom typography
- **Responsive Design** - Mobile-first approach

### Key Features
- Multi-step registration process
- PIX payment integration
- SMS notifications via SMSDEV API
- Session-based data persistence
- Real-time payment status checking
- External API integration for user data

### API Integrations
- Payment processing API
- SMSDEV SMS service
- External customer data API (webhook-manager.replit.app)

## File Structure
```
├── app.py              # Main Flask application
├── main.py            # Application entry point
├── models.py          # Database models
├── payments.py        # Payment processing logic
├── sms_service.py     # SMS notification service
├── templates/         # Jinja2 templates
├── static/           # Static assets (CSS, JS, images)
└── requirements.txt  # Python dependencies
```

## Configuration
- Environment variables for database, secrets, and API keys
- Development/production environment detection
- Auto-deployment support via Replit

## Current Issues
- Tailwind CSS CDN warning for production use
- Missing SMSDEV_API_KEY configuration

## User Preferences
- Portuguese language interface
- Military/government aesthetic
- Professional, secure appearance
- Mobile-responsive design

## Recent Changes
- Initial project setup complete
- Multi-step registration flow implemented
- PIX payment integration functional
- SMS service integration ready (pending API key)

## Next Steps
1. Replace Tailwind CDN with proper production setup
2. Configure SMSDEV API key
3. Optimize for production deployment