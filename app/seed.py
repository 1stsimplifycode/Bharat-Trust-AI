"""
Seed realistic dummy data.

Generates sellers, products, reviews, orders, returns and complaints. Crucially
it PLANTS real anomalies (shared GST/phone/IP rings, review-farm templates,
counterfeit-priced premium goods) so the agents detect genuine signal rather
than noise. Idempotent: drops + recreates tables.

Run:  python -m app.seed         (from backend/)
"""
import random
from datetime import datetime, timedelta

from .database import Base, engine, SessionLocal
from . import models

random.seed(7)

STATES = [
    ("Karnataka", "Bengaluru", 12.97, 77.59),
    ("Maharashtra", "Mumbai", 19.07, 72.87),
    ("Delhi", "New Delhi", 28.70, 77.10),
    ("West Bengal", "Kolkata", 22.57, 88.36),
    ("Tamil Nadu", "Chennai", 13.08, 80.27),
    ("Telangana", "Hyderabad", 17.38, 78.48),
    ("Gujarat", "Ahmedabad", 23.02, 72.57),
    ("Rajasthan", "Jaipur", 26.91, 75.78),
]
CATEGORIES = {
    "Apparel": ["Cotton Kurta", "Denim Jeans", "Saree", "T-Shirt", "Jacket"],
    "Footwear": ["Running Shoes", "Sandals", "Sneakers", "Formal Shoes"],
    "Electronics": ["Bluetooth Earbuds", "Power Bank", "Smartwatch", "USB Charger"],
    "Beauty": ["Face Cream", "Lipstick", "Shampoo", "Serum"],
    "Home": ["Bedsheet", "Curtains", "Wall Clock", "Cushion Cover"],
    "Kitchen": ["Steel Bottle", "Pressure Cooker", "Knife Set", "Lunch Box"],
    "Grocery": ["Basmati Rice 5kg", "Cold Pressed Oil", "Almonds 500g"],
    "Books": ["Fiction Novel", "Exam Guide", "Cookbook"],
}
BRANDS = ["Nike", "Adidas", "Boat", "Puma", "Samsung", "Sony", "Generic",
          "Local Co", "Bharat Goods", "Apple"]
REVIEW_GENUINE = [
    "Fabric quality is decent for the price, fits as expected after one wash.",
    "Delivery took 4 days. Product matches the photos, packaging was sealed.",
    "Battery lasts about a day and a half, charging is reasonably quick.",
    "Slightly tighter than my usual size, otherwise comfortable for daily use.",
    "Works fine so far, the build feels sturdy and the colour is accurate.",
]
REVIEW_FARM = "Best product must buy highly recommend value for money superb"

CITIES = STATES


def gen():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()

    sellers = []
    for i in range(500):
        st = random.choice(STATES)
        # honest baseline behaviour
        cancel = round(random.betavariate(2, 18), 3)            # ~0.1 mean
        delay = round(random.betavariate(2, 8) * 6, 2)          # 0..~4 days
        complaints = random.randint(0, 6)
        volatility = round(random.betavariate(2, 12), 3)
        velocity = round(random.uniform(0.5, 6), 2)
        s = models.Seller(
            name=f"Seller {i+1:03d}",
            gst_number=f"GST{random.randint(10**9, 10**10):010d}",
            phone=f"9{random.randint(10**8, 10**9 - 1)}",
            ip_address=f"49.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}",
            state=st[0], city=st[1], lat=st[2], lng=st[3],
            verified_invoices=random.random() > 0.3,
            total_orders=random.randint(20, 4000),
            cancellation_rate=cancel,
            avg_delivery_delay_days=delay,
            complaint_count=complaints,
            price_volatility=volatility,
            review_velocity=velocity,
        )
        sellers.append(s)
    db.add_all(sellers)
    db.commit()

    # ---- PLANT FRAUD RINGS (genuine signal for the agents) ----
    # Ring A: 4 sellers share a GST number
    shared_gst = "GST9999999001"
    for s in random.sample(sellers, 4):
        s.gst_number = shared_gst
    # Ring B: 3 sellers share a phone + IP and behave badly
    shared_phone, shared_ip = "9800000000", "203.0.113.45"
    for s in random.sample(sellers, 3):
        s.phone = shared_phone
        s.ip_address = shared_ip
        s.cancellation_rate = round(random.uniform(0.3, 0.5), 3)
        s.review_velocity = round(random.uniform(20, 40), 2)
        s.complaint_count = random.randint(15, 40)
        s.verified_invoices = False
    db.commit()

    # ---- PRODUCTS (3000) ----
    products = []
    for i in range(3000):
        seller = random.choice(sellers)
        cat = random.choice(list(CATEGORIES))
        name = random.choice(CATEGORIES[cat])
        brand = random.choice(BRANDS)
        mrp = round(random.uniform(200, 8000), -1)
        # most priced sensibly; a few premium brands suspiciously cheap (counterfeit)
        if brand in {"Nike", "Adidas", "Apple", "Samsung", "Sony"} and random.random() < 0.15:
            price = round(mrp * random.uniform(0.2, 0.35), -1)   # counterfeit signal
        else:
            price = round(mrp * random.uniform(0.6, 0.95), -1)
        p = models.Product(
            seller_id=seller.id, name=f"{brand} {name}", brand=brand, category=cat,
            price=price, mrp=mrp,
            has_qr=random.random() > 0.4, has_invoice=random.random() > 0.3,
            description=f"{brand} {name} in {cat.lower()} category. Genuine quality, fast shipping.",
            image_url=f"https://picsum.photos/seed/{i}/300/300",
        )
        products.append(p)
    db.add_all(products)
    db.commit()

    # ---- REVIEWS (5000), some farmed ----
    reviews = []
    for i in range(5000):
        p = random.choice(products)
        if random.random() < 0.12:        # 12% farmed/templated reviews
            text = REVIEW_FARM
            rating = 5
        else:
            text = random.choice(REVIEW_GENUINE)
            rating = random.choices([5, 4, 3, 2, 1], [40, 30, 15, 10, 5])[0]
        reviews.append(models.Review(
            product_id=p.id, customer_name=f"User{random.randint(1, 9000)}",
            rating=rating, text=text,
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 180)),
        ))
    db.add_all(reviews)
    db.commit()

    # update product rating aggregates
    from sqlalchemy import func
    agg = (db.query(models.Review.product_id,
                    func.avg(models.Review.rating), func.count(models.Review.id))
           .group_by(models.Review.product_id).all())
    amap = {pid: (round(avg, 2), cnt) for pid, avg, cnt in agg}
    for p in products:
        if p.id in amap:
            p.avg_rating, p.rating_count = amap[p.id]
    db.commit()

    # ---- ORDERS (1000) + returns + complaints ----
    orders, returns, complaints = [], [], []
    for i in range(1000):
        p = random.choice(products)
        st = random.choice(CITIES)
        status = random.choices(
            ["delivered", "shipped", "placed", "cancelled", "returned"],
            [55, 15, 10, 8, 12])[0]
        o = models.Order(
            product_id=p.id, seller_id=p.seller_id,
            customer_name=f"Cust{random.randint(1, 9000)}",
            customer_state=st[0], quantity=random.randint(1, 3),
            amount=p.price, status=status,
            delivery_days=random.randint(1, 9),
            placed_at=datetime.utcnow() - timedelta(days=random.randint(0, 120)),
        )
        orders.append(o)
    db.add_all(orders)
    db.commit()

    for o in orders:
        if o.status == "returned":
            returns.append(models.Return(
                order_id=o.id,
                reason=random.choice(["Size issue", "Damaged", "Not as described",
                                      "Quality", "Wrong item"]),
            ))
        if random.random() < 0.06:
            complaints.append(models.Complaint(
                seller_id=o.seller_id, order_id=o.id, customer_name=o.customer_name,
                category=random.choice(["counterfeit", "delay", "damaged", "refund"]),
                text="Customer reported an issue with this order.",
            ))
    db.add_all(returns)
    db.add_all(complaints)
    db.commit()

    print(f"Seeded: {len(sellers)} sellers, {len(products)} products, "
          f"{len(reviews)} reviews, {len(orders)} orders, "
          f"{len(returns)} returns, {len(complaints)} complaints.")
    print(f"Planted: GST ring (4 sellers), phone+IP ring (3 sellers), "
          f"counterfeit-priced premium goods, review farms.")
    db.close()


if __name__ == "__main__":
    gen()
