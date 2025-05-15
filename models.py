from datetime import datetime
from app import db
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship


class Transaction(db.Model):
    """Model for storing API transaction data between GHL and Clio"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(20), nullable=False)  # 'ghl' or 'clio'
    destination = Column(String(20), nullable=False)  # 'ghl' or 'clio'
    request_method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    request_url = Column(String(255), nullable=False)
    request_headers = Column(JSON, nullable=True)
    request_body = Column(JSON, nullable=True)
    response_status = Column(Integer, nullable=True)
    response_headers = Column(JSON, nullable=True)
    response_body = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationship with error logs
    error_logs = relationship("ErrorLog", back_populates="transaction")
    
    def __repr__(self):
        return f"<Transaction {self.id}: {self.source} to {self.destination} - Status: {self.response_status}>"


class ErrorLog(db.Model):
    """Model for storing error logs related to API transactions"""
    __tablename__ = "error_logs"
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    error_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationship with transactions
    transaction = relationship("Transaction", back_populates="error_logs")
    
    def __repr__(self):
        return f"<ErrorLog {self.id}: {self.error_type} - {self.error_message[:50]}>"


class ApiConfig(db.Model):
    """Model for storing API configuration for GHL and Clio"""
    __tablename__ = "api_configs"
    
    id = Column(Integer, primary_key=True)
    service = Column(String(20), nullable=False, unique=True)  # 'ghl' or 'clio'
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    base_url = Column(String(255), nullable=True)
    oauth_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    refresh_token = Column(Text, nullable=True)
    additional_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<ApiConfig {self.id}: {self.service} - Active: {self.is_active}>"


class DataMapping(db.Model):
    """Model for storing data field mappings between GHL and Clio"""
    __tablename__ = "data_mappings"
    
    id = Column(Integer, primary_key=True)
    ghl_field = Column(String(100), nullable=False)
    clio_field = Column(String(100), nullable=False)
    mapping_type = Column(String(20), nullable=False, default="direct")  # direct, transform, custom
    transform_logic = Column(Text, nullable=True)  # For custom transformations if needed
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<DataMapping {self.id}: {self.ghl_field} -> {self.clio_field}>"
