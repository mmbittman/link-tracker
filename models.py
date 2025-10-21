from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Link(db.Model):
    __tablename__ = "links"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)  # e.g. "insta" or "shop"
    destination = db.Column(db.String(200), nullable=False)       # real URL to redirect to
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Click(db.Model):
    __tablename__ = "clicks"
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip = db.Column(db.String(50))
    user_agent = db.Column(db.String(300))
    referrer = db.Column(db.String(300))
    # optional: add country, city if you later add a geo IP lookup

    link = db.relationship("Link", backref="clicks")
