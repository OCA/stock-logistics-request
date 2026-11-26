# Copyright 2020-24 ForgeFlow S.L. (https://www.forgeflow.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import float_compare

logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    The objective of this hook is to link existing MOs
    coming from a Stock Request.
    """
    logger.info("Linking existing MOs coming from a Stock Request")
    link_existing_mos_to_stock_request(env)
    recompute_kit_requests(env)


def recompute_kit_requests(env):
    """The stored quantities of the requests of kits were computed with the
    quantities of the components. Compute them again in kits, and let the
    requests that were closed too early follow them."""
    env = api.Environment(env.cr, SUPERUSER_ID, dict())
    requests = env["stock.request"].search(
        [
            ("allocation_ids", "!=", False),
            ("product_id.product_tmpl_id.bom_ids.type", "=", "phantom"),
        ]
    )
    if not requests:
        return
    logger.info(f"Recomputing the quantities of {len(requests)} requests of kits")
    fnames = ["qty_done", "qty_in_progress", "qty_cancelled"]
    for fname in fnames:
        env.add_to_compute(requests._fields[fname], requests)
    requests.flush_recordset(fnames)
    precision = env["decimal.precision"].precision_get("Product Unit")
    in_progress = requests.filtered(
        lambda r: float_compare(r.qty_in_progress, 0, precision_digits=precision) > 0
    )
    (in_progress & requests.filtered(lambda r: r.state in ("done", "cancel"))).write(
        {"state": "open"}
    )
    (requests - in_progress).filtered(lambda r: r.state == "open").check_done()


def link_existing_mos_to_stock_request(env):
    env = api.Environment(env.cr, SUPERUSER_ID, dict())
    stock_request_obj = env["stock.request"]
    stock_request_order_obj = env["stock.request.order"]
    stock_request_allocation_obj = env["stock.request.allocation"]
    mrp_production_obj = env["mrp.production"]
    mos_with_sr = mrp_production_obj.search([("origin", "ilike", "SR/%")])
    logger.info(f"Linking {len(mos_with_sr)} MOs records")
    stock_requests = stock_request_obj.search(
        [("name", "in", [mo.origin for mo in mos_with_sr])]
    )
    for mo in mos_with_sr:
        stock_request = stock_requests.filtered(lambda x, mo=mo: x.name == mo.origin)
        if stock_request:
            # Link SR to MO
            mo.stock_request_ids = [(6, 0, stock_request.ids)]
            logger.info(f"MO {mo.name} linked to SR {stock_request.name}")
            if (
                not stock_request_allocation_obj.search(
                    [("stock_request_id", "=", stock_request.id)]
                )
                and mo.state != "cancel"
            ):
                # Create allocation for finish move
                logger.info(f"Create allocation for {stock_request.name}")
                mo.move_finished_ids[0].allocation_ids = [
                    (
                        0,
                        0,
                        {
                            "stock_request_id": request.id,
                            "requested_product_uom_qty": request.product_qty,
                        },
                    )
                    for request in mo.stock_request_ids
                ]

            # Update allocations
            logger.info(f"Updating Allocations for SR {stock_request.name}")
            for ml in mo.finished_move_line_ids.filtered(
                lambda m: m.exists() and m.move_id.allocation_ids
            ):
                quantity = ml.product_uom_id._compute_quantity(
                    ml.quantity, ml.product_id.uom_id
                )
                to_allocate_qty = ml.quantity
                for allocation in ml.move_id.allocation_ids:
                    if allocation.open_product_qty:
                        allocated_qty = min(allocation.open_product_qty, quantity)
                        allocation.allocated_product_qty += allocated_qty
                        to_allocate_qty -= allocated_qty
            stock_request.check_done()
    # Update production_ids from SROs
    stock_request_order_obj.search([])._compute_production_ids()
