# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import SUPERUSER_ID, api
from odoo.tools import float_compare


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    allocations = env["stock.request.allocation"].search(
        [("stock_move_id.purchase_line_id", "!=", False)]
    )
    requests = env["stock.request"]
    for allocation in allocations:
        request = allocation.stock_request_id
        # It was stored in the UoM of the product instead of that of the request
        if float_compare(
            allocation.requested_product_uom_qty, request.product_qty, 4
        ) == 0 and float_compare(request.product_qty, request.product_uom_qty, 4):
            allocation.requested_product_uom_qty = request.product_uom_qty
            requests |= request
    # qty_in_progress is stored and does not depend on the allocated quantity
    requests._compute_qty()
