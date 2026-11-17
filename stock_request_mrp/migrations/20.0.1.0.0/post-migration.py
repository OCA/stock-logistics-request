# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from collections import Counter

from odoo import SUPERUSER_ID, Command, api
from odoo.tools import float_compare

QTY_FIELDS = ["qty_done", "qty_in_progress", "qty_cancelled"]


def _get_main_finished_move(production):
    return production.move_finished_ids.filtered(
        lambda m: (
            m.product_id == production.product_id
            and not m.byproduct_id
            and m.state != "cancel"
        )
    )[:1]


def _is_merge_candidate(request, production):
    """The request may have been merged into the production: same product,
    company and warehouse, a manufacturing route, and created before the
    production was done."""
    route = request.route_id
    return (
        request.product_id == production.product_id
        and request.company_id == production.company_id
        and request.warehouse_id == production.picking_type_id.warehouse_id
        and (not route or "manufacture" in route.rule_ids.mapped("action"))
        and (
            production.state != "done"
            or not production.date_finished
            or request.create_date <= production.date_finished
        )
    )


def _link_merged_requests(env):
    """Previous versions only increased the quantity of an existing production
    when a request was merged into it, and left the request without production.
    Link the open requests without allocations to the production whose extra
    quantity they match exactly, and leave them as they are when the match is
    not certain."""
    requests = env["stock.request"].search(
        [
            ("state", "=", "open"),
            ("production_ids", "=", False),
            ("allocation_ids", "=", False),
        ]
    )
    if not requests:
        return requests
    # A backorder splits the quantity of the production, so its extra
    # quantity cannot be told apart
    productions = env["mrp.production"].search(
        [
            ("product_id", "in", requests.product_id.ids),
            ("stock_request_ids", "!=", False),
            ("state", "!=", "cancel"),
            ("backorder_sequence", "=", 0),
        ],
        order="id",
    )
    matches = {}
    for production in productions:
        move = _get_main_finished_move(production)
        if not move:
            continue
        product_uom = production.product_id.uom_id
        # product_uom_qty is the quantity of the production in the product UoM
        extra_qty = production.product_uom_qty - sum(
            move.allocation_ids.mapped("requested_product_qty")
        )
        candidates = requests.filtered(
            lambda r, production=production: _is_merge_candidate(r, production)
        )
        if candidates and not product_uom.compare(
            sum(candidates.mapped("product_qty")), extra_qty
        ):
            matches[production] = candidates
    # A request that matches more than one production is not certain
    match_count = Counter(r for candidates in matches.values() for r in candidates)
    linked = env["stock.request"]
    for production, candidates in matches.items():
        if any(match_count[r] > 1 for r in candidates):
            continue
        production.stock_request_ids = [Command.link(r.id) for r in candidates]
        linked |= candidates
        move = _get_main_finished_move(production)
        if move.state != "done":
            candidates._update_production_allocations()
            continue
        # The open quantity of a done move is zero, so allocate the done
        # quantity that the other requests did not take
        product_uom = move.product_id.uom_id
        done_qty = sum(
            ml.uom_id._compute_quantity(ml.quantity, product_uom)
            for ml in move.move_line_ids
        ) - sum(move.allocation_ids.mapped("allocated_product_qty"))
        for request in candidates:
            allocated_qty = max(min(request.product_qty, done_qty), 0.0)
            done_qty -= allocated_qty
            env["stock.request.allocation"].create(
                {
                    "stock_request_id": request.id,
                    "stock_move_id": move.id,
                    "requested_product_uom_qty": request.product_uom_qty,
                    "allocated_product_qty": allocated_qty,
                }
            )
    return linked


def migrate(cr, version):
    """Fix the allocations of manufacturing orders stored in previous versions:
    the byproducts were allocated to the request, so they counted as done
    twice, and backorders and batch sizes got the full quantity of the
    request. Remove the byproduct allocations, spread the quantity of each
    request over its open productions, reopen the requests that the
    byproducts closed too early and link the requests merged into an
    existing production."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    production_allocations = env["stock.request.allocation"].search(
        [("stock_move_id.production_id", "!=", False)]
    )
    byproduct_allocations = production_allocations.filtered(
        "stock_move_id.byproduct_id"
    )
    requests = production_allocations.stock_request_id
    precision = env["decimal.precision"].precision_get("Product Unit")
    # Only reopen the requests closed because the byproducts completed them,
    # not the ones closed by hand
    closed_by_byproducts = byproduct_allocations.stock_request_id.filtered(
        lambda r: (
            r.state == "done"
            and float_compare(r.qty_done, r.product_uom_qty, precision_digits=precision)
            >= 0
        )
    )
    byproduct_allocations.unlink()
    requests._update_production_allocations()
    for fname in QTY_FIELDS:
        env.add_to_compute(requests._fields[fname], requests)
    requests.flush_recordset(QTY_FIELDS)
    for request in closed_by_byproducts:
        if (
            float_compare(
                request.qty_done, request.product_uom_qty, precision_digits=precision
            )
            < 0
            and request.qty_in_progress > 0
        ):
            request.state = "open"
    linked = _link_merged_requests(env)
    for fname in QTY_FIELDS:
        env.add_to_compute(linked._fields[fname], linked)
    linked.flush_recordset(QTY_FIELDS)
    linked.check_done()
