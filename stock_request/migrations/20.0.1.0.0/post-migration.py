# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import SUPERUSER_ID, api

QTY_FIELDS = ["qty_done", "qty_in_progress", "qty_cancelled"]


def _get_pending_qty(alloc):
    """Quantity of the request not fulfilled by the done moves."""
    request = alloc.stock_request_id
    fulfilled_qty = sum(
        other.allocated_product_qty
        for other in request.allocation_ids - alloc
        if other.stock_move_id.state == "done" and other._get_done_sign() > 0
    )
    return max(request.product_qty - fulfilled_qty, 0.0)


def _fix_open_allocations(env):
    """A backorder copied the full requested quantity of its allocations.
    Limit the open quantity of each allocation of an open move to what its
    request still needs, and of each open move to what the move still moves."""
    allocations = env["stock.request.allocation"].search(
        [("stock_move_id.state", "not in", ["done", "cancel"])]
    )
    for move in allocations.stock_move_id:
        product_uom = move.product_id.uom_id
        to_allocate = move.product_qty
        for alloc in move.allocation_ids:
            qty = min(alloc.open_product_qty, _get_pending_qty(alloc), to_allocate)
            to_allocate -= qty
            if not product_uom.compare(qty, alloc.open_product_qty):
                continue
            alloc.requested_product_uom_qty = product_uom._compute_quantity(
                alloc.allocated_product_qty + qty,
                alloc.product_uom_id,
                rounding_method="HALF-UP",
            )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _fix_open_allocations(env)
    # The stored quantities counted returns and pushed moves twice
    requests = env["stock.request"].search([("allocation_ids", "!=", False)])
    for fname in QTY_FIELDS:
        env.add_to_compute(requests._fields[fname], requests)
    requests.flush_recordset(QTY_FIELDS)
