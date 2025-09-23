
def migrate(cr, version):
    cr.execute("""
    UPDATE ir_model_data
    SET name = 'stock_request_order_form'
    WHERE module = 'stock_request_partner' AND name = 'view_stock_request_order_real';
    """
    )
