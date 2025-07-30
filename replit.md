# GHL API Clio Integration

## Overview

This is a Flask-based web application that provides API integration between GoHighLevel (GHL) and Clio legal practice management platforms. The system serves as a middleware that facilitates data synchronization, transaction logging, and error monitoring between the two platforms.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 with Flask
- **UI Framework**: Bootstrap 5 with dark theme
- **JavaScript**: Vanilla JavaScript with Bootstrap components
- **Styling**: Custom CSS with responsive design

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **Database ORM**: SQLAlchemy
- **Session Management**: Flask sessions with OAuth support
- **API Integration**: RESTful API clients for both GHL and Clio
- **Service Layer**: Modular service architecture with separate services for each platform

### Database Schema
The application uses SQLAlchemy models with the following key entities:
- **Transaction**: Logs API transactions between platforms
- **ErrorLog**: Tracks errors related to API transactions
- **ApiConfig**: Stores API configuration for both services
- **DataMapping**: Handles field mapping between platforms

## Key Components

### Core Services
1. **GHLService**: Handles GoHighLevel API interactions
2. **ClioService**: Manages Clio API communication with OAuth support
3. **IntegrationService**: Orchestrates data synchronization between platforms

### Authentication & Authorization
- OAuth 2.0 flow for Clio integration
- API key-based authentication for GoHighLevel
- Session-based user authentication with decorators

### Web Interface Components
- **Dashboard**: Real-time metrics and system status
- **Transaction Logs**: Detailed API transaction history
- **Error Monitoring**: Comprehensive error tracking and analysis
- **Settings Management**: Configuration interface for both platforms
- **Data Mapping**: Field mapping configuration between systems

### Utility Scripts
- **Database Testing**: Connection validation utilities
- **Log Analysis**: Transaction monitoring and reporting tools

## Data Flow

1. **Inbound Requests**: Web interface receives user interactions
2. **Service Layer**: Routes requests to appropriate service (GHL/Clio)
3. **API Communication**: Services make authenticated API calls
4. **Transaction Logging**: All API interactions are logged to database
5. **Error Handling**: Failures are captured and stored for analysis
6. **Response Processing**: Results are formatted and returned to frontend

### Integration Patterns
- **Bidirectional Sync**: Data flows both ways between platforms
- **Field Mapping**: Configurable field mapping between different data models
- **Practice Area Detection**: Intelligent categorization based on description text
- **Conflict Resolution**: Handling of duplicate or conflicting data

## External Dependencies

### Third-Party APIs
- **GoHighLevel API**: CRM and marketing automation platform
- **Clio API**: Legal practice management system

### Frontend Libraries
- Bootstrap 5 (dark theme variant)
- Bootstrap Icons
- Custom CSS for application-specific styling

### Backend Libraries
- Flask web framework
- SQLAlchemy ORM
- Requests library for HTTP communication
- psycopg2 for PostgreSQL connectivity

### Environment Variables
- `SECRET_KEY`: Flask session encryption
- `DATABASE_URL`: PostgreSQL connection string
- `CLIO_CLIENT_ID` & `CLIO_CLIENT_SECRET`: OAuth credentials
- `GHL_API_KEY`: GoHighLevel authentication
- Various service-specific configuration parameters

## Deployment Strategy

### Database Requirements
- PostgreSQL database (configurable via DATABASE_URL)
- Automatic table creation via SQLAlchemy models
- Connection pooling and error handling

### Environment Configuration
- Environment variable-based configuration
- Fallback to hardcoded defaults for development
- OAuth redirect URI configuration for Clio integration

### Application Structure
- Modular service architecture for easy maintenance
- Separation of concerns between data access, business logic, and presentation
- Comprehensive logging and error tracking for production monitoring

### Backup System
- Automated backup functionality with timestamped snapshots
- File-based backup storage in `/backups` directory
- Configuration and code preservation for rollback capabilities