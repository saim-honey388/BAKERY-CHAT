# Database Schema Analysis and Fix Plan

## Problem Analysis

Based on the error log provided:
```
TypeError: 'total_amount' is an invalid keyword argument for Order
```

The issue is that the `Order` model in `models.py` defines a `total_amount` field (line 46), but the actual database table `orders` doesn't have this column. This happens when:

1. The database was created before the `total_amount` field was added to the model
2. No migration was run to add the column to the existing database
3. The code tries to create an Order instance with `total_amount=cart.get_total()` but the database schema doesn't support it

## Current Model Definition (models.py line 46)
```python
total_amount = Column(Float, nullable=False)  # Added field to store total order amount
```

## Current Code Usage (order_agent.py lines 268, 476)
```python
order = Order(
    customer_id=customer.id,
    status=OrderStatus.pending,
    pickup_or_delivery=FulfillmentType.pickup if cart.fulfillment_type == 'pickup' else FulfillmentType.delivery,
    total_amount=cart.get_total()  # This line causes the error
)
```

## Root Cause
The database table `orders` was created without the `total_amount` column, but the SQLAlchemy model expects it to exist.

## Solution Steps

### 1. Database Schema Inspection
- Check current `orders` table structure in `bakery.db`
- Confirm missing `total_amount` column

### 2. Create Alembic Migration
- Generate migration to add `total_amount` column
- Set appropriate default value for existing records
- Make column nullable initially, then update existing records

### 3. Migration Content
```sql
ALTER TABLE orders ADD COLUMN total_amount FLOAT;
```

### 4. Handle Existing Data
- Calculate total_amount for existing orders based on their OrderItems
- Update existing records with calculated totals

### 5. Test the Fix
- Run migration
- Test order creation flow
- Verify existing orders still work

## Files to Modify

1. **Create new migration file** in `migrations/versions/`
2. **Verify models.py** - ensure it matches intended schema
3. **Test order_agent.py** - ensure _finalize_order works after fix

## Migration Strategy

Since there are existing orders in the database (as shown in the log), we need to:

1. Add the column as nullable first
2. Calculate and populate total_amount for existing orders
3. Make the column non-nullable (optional, based on requirements)

## Expected Outcome

After applying the migration:
- `total_amount` column will exist in the `orders` table
- Existing orders will have calculated total amounts
- New orders can be created successfully with total_amount
- The order finalization process will work without errors