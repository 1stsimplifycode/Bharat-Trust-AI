"""
ORM models — normalized marketplace schema.

Entities: Seller, Product, Review, Order, Return, Complaint, FraudEvent,
TrustScore, LogisticsRoute, AIReport. Relationships and indexes included.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


class Seller(Base):
    __tablename__ = "sellers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    gst_number = Column(String, index=True)        # used for duplicate / fraud detection
    phone = Column(String, index=True)
    ip_address = Column(String, index=True)
    state = Column(String, index=True)
    city = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    verified_invoices = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    # behavioural aggregates (kept denormalized for fast agent scoring)
    total_orders = Column(Integer, default=0)
    cancellation_rate = Column(Float, default=0.0)   # 0..1
    avg_delivery_delay_days = Column(Float, default=0.0)
    complaint_count = Column(Integer, default=0)
    price_volatility = Column(Float, default=0.0)    # std/mean of price changes
    review_velocity = Column(Float, default=0.0)     # reviews per day (spike = suspicious)

    products = relationship("Product", back_populates="seller")
    trust_scores = relationship("TrustScore", back_populates="seller")
    fraud_events = relationship("FraudEvent", back_populates="seller")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), index=True)
    name = Column(String, nullable=False)
    brand = Column(String, index=True)
    category = Column(String, index=True)
    price = Column(Float)
    mrp = Column(Float)
    has_qr = Column(Boolean, default=False)
    has_invoice = Column(Boolean, default=False)
    description = Column(Text)
    image_url = Column(String)
    avg_rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    seller = relationship("Seller", back_populates="products")
    reviews = relationship("Review", back_populates="product")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    customer_name = Column(String)
    rating = Column(Integer)
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    authenticity_score = Column(Float, default=None)   # filled by Review Intelligence Agent

    product = relationship("Product", back_populates="reviews")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), index=True)
    customer_name = Column(String)
    customer_state = Column(String, index=True)
    quantity = Column(Integer, default=1)
    amount = Column(Float)
    status = Column(String, default="placed")     # placed|shipped|delivered|cancelled|returned
    delivery_days = Column(Integer, default=0)
    placed_at = Column(DateTime, default=datetime.utcnow)
    return_probability = Column(Float, default=None)  # filled by Return Prediction Agent


class Return(Base):
    __tablename__ = "returns"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    reason = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    customer_name = Column(String)
    category = Column(String)     # counterfeit|delay|damaged|wrong_item|refund
    text = Column(Text)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=datetime.utcnow)


class FraudEvent(Base):
    __tablename__ = "fraud_events"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), index=True)
    kind = Column(String)         # duplicate_gst|duplicate_phone|duplicate_ip|anomaly|review_farm
    severity = Column(Float)      # 0..1
    detail = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow)

    seller = relationship("Seller", back_populates="fraud_events")


class TrustScore(Base):
    __tablename__ = "trust_scores"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), index=True)
    seller_score = Column(Float)
    fraud_score = Column(Float)
    return_score = Column(Float)
    authenticity_score = Column(Float)
    review_score = Column(Float)
    delivery_score = Column(Float)
    overall = Column(Float)
    reasoning = Column(Text)       # JSON list of reasons
    computed_at = Column(DateTime, default=datetime.utcnow)

    seller = relationship("Seller", back_populates="trust_scores")


class LogisticsRoute(Base):
    __tablename__ = "logistics_routes"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    warehouse = Column(String)
    courier = Column(String)
    distance_km = Column(Float)
    eta_days = Column(Float)
    cost = Column(Float)
    baseline_cost = Column(Float)
    savings = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class AIReport(Base):
    __tablename__ = "ai_reports"
    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String)        # seller:<id> | marketplace | weekly
    title = Column(String)
    body = Column(Text)           # JSON payload of the structured report
    created_at = Column(DateTime, default=datetime.utcnow)


# Composite indexes for common analytic queries
Index("ix_orders_seller_status", Order.seller_id, Order.status)
Index("ix_products_cat_brand", Product.category, Product.brand)
