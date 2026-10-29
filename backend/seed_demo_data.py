"""Seed script to populate realistic restaurant categories and menu items for demo testing."""
import sys
from decimal import Decimal
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import SessionLocal
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.table import RestaurantTable


def seed_database():
    db = SessionLocal()
    try:
        # Check and seed tables if empty
        if db.query(RestaurantTable).count() == 0:
            print("Seeding restaurant tables...")
            tables_data = [
                {"table_number": "T-1", "capacity": 2, "status": "available"},
                {"table_number": "T-2", "capacity": 2, "status": "occupied"},
                {"table_number": "T-3", "capacity": 4, "status": "available"},
                {"table_number": "T-4", "capacity": 4, "status": "occupied"},
                {"table_number": "T-5", "capacity": 4, "status": "reserved"},
                {"table_number": "T-6", "capacity": 6, "status": "available"},
                {"table_number": "Patio-1", "capacity": 4, "status": "available"},
                {"table_number": "Patio-2", "capacity": 4, "status": "reserved"},
                {"table_number": "Booth-A", "capacity": 8, "status": "occupied"},
                {"table_number": "Booth-B", "capacity": 6, "status": "available"},
            ]
            for t_data in tables_data:
                db.add(RestaurantTable(**t_data))
            db.commit()
            print("Tables seeded successfully.")
        else:
            print("Tables already exist. Skipping table seed.")

        # Check if categories already exist
        if db.query(Category).count() > 0:
            print("Database already contains categories. Skipping menu seed to preserve data.")
            return

        print("Seeding initial categories...")
        categories_data = [
            {
                "name": "Starters & Appetizers",
                "description": "Crispy bites and palate cleansers to start your dining journey.",
            },
            {
                "name": "Wood-Fired Pizza",
                "description": "Hand-stretched artisanal Neapolitan crusts baked at 800°F.",
            },
            {
                "name": "Pasta & Mains",
                "description": "House-crafted pastas and signature chef specialties.",
            },
            {
                "name": "Craft Beverages",
                "description": "Fresh pressed juices, specialty coffees, and mocktails.",
            },
            {
                "name": "Desserts",
                "description": "Decadent sweet endings made fresh daily in-house.",
            },
        ]

        category_instances = {}
        for cat in categories_data:
            c = Category(name=cat["name"], description=cat["description"])
            db.add(c)
            db.flush()
            category_instances[cat["name"]] = c

        print("Seeding initial menu items...")
        menu_items_data = [
            {
                "category": "Starters & Appetizers",
                "name": "Truffle Arancini",
                "price": Decimal("11.50"),
                "description": "Crispy carnaroli risotto balls filled with wild mushrooms and taleggio cheese.",
                "prep_time_minutes": 10,
                "is_available": True,
            },
            {
                "category": "Starters & Appetizers",
                "name": "Bruschetta Pomodoro",
                "price": Decimal("8.50"),
                "description": "Toasted rustic sourdough topped with heirloom tomatoes, garlic, extra virgin olive oil, and fresh basil.",
                "prep_time_minutes": 8,
                "is_available": True,
            },
            {
                "category": "Wood-Fired Pizza",
                "name": "Margherita Classica",
                "price": Decimal("16.00"),
                "description": "San Marzano tomato sauce, fresh buffalo mozzarella, fresh basil, and extra virgin olive oil.",
                "prep_time_minutes": 12,
                "is_available": True,
            },
            {
                "category": "Wood-Fired Pizza",
                "name": "Spicy Diavola",
                "price": Decimal("18.50"),
                "description": "Calabrian chili oil, spicy artisanal soppressata, crushed tomatoes, and smoked provolone.",
                "prep_time_minutes": 14,
                "is_available": True,
            },
            {
                "category": "Wood-Fired Pizza",
                "name": "Tartufo Bianco Pizza",
                "price": Decimal("22.00"),
                "description": "White truffle cream, fior di latte mozzarella, roasted portobello mushrooms, and rosemary.",
                "prep_time_minutes": 15,
                "is_available": False,  # Test out-of-stock item
            },
            {
                "category": "Pasta & Mains",
                "name": "Fettuccine Truffle Alfredo",
                "price": Decimal("21.50"),
                "description": "Fresh egg pasta tossed with 24-month aged parmigiano-reggiano and black truffle shaving.",
                "prep_time_minutes": 18,
                "is_available": True,
            },
            {
                "category": "Pasta & Mains",
                "name": "Grilled Salmon Fillet",
                "price": Decimal("24.95"),
                "description": "Wild Atlantic salmon served with lemon herb reduction and roasted asparagus.",
                "prep_time_minutes": 20,
                "is_available": True,
            },
            {
                "category": "Craft Beverages",
                "name": "Cold Brew Espresso",
                "price": Decimal("5.50"),
                "description": "Single-origin Ethiopian beans steeped for 18 hours, served over clear craft ice sphere.",
                "prep_time_minutes": 3,
                "is_available": True,
            },
            {
                "category": "Craft Beverages",
                "name": "Blood Orange Spritz",
                "price": Decimal("7.00"),
                "description": "Sparkling Sicilian blood orange soda with fresh mint and citrus twist.",
                "prep_time_minutes": 4,
                "is_available": True,
            },
            {
                "category": "Desserts",
                "name": "Classic Tiramisu",
                "price": Decimal("9.50"),
                "description": "Espresso-soaked savoiardi ladyfingers layered with rich mascarpone zabaglione and cocoa.",
                "prep_time_minutes": 5,
                "is_available": True,
            },
        ]

        for item in menu_items_data:
            cat_obj = category_instances[item["category"]]
            m = MenuItem(
                category_id=cat_obj.id,
                name=item["name"],
                description=item["description"],
                price=item["price"],
                prep_time_minutes=item["prep_time_minutes"],
                is_available=item["is_available"],
            )
            db.add(m)

        db.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
