# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo import Command, api, fields, models


class StockRequestOrder(models.Model):
    _inherit = "stock.request.order"

    # Technical fields for the product_matrix grid entry. They are never
    # stored: `grid` either holds the matrix to open or the changes to apply,
    # depending on `grid_update`.
    grid_product_tmpl_id = fields.Many2one(
        "product.template",
        store=False,
        help="Technical field for product_matrix functionalities.",
    )
    grid_update = fields.Boolean(
        default=False,
        store=False,
        help="Whether the grid field contains a new matrix to apply or not.",
    )
    grid = fields.Char(
        store=False,
        help="Technical storage of grid.\n"
        "If grid_update, will be loaded on the order.\n"
        "If not, represents the matrix to open.",
    )

    @api.onchange("grid_product_tmpl_id")
    def _set_grid_up(self):
        self.ensure_one()
        if self.grid_product_tmpl_id:
            self.grid_update = False
            self.grid = json.dumps(self._get_matrix(self.grid_product_tmpl_id))

    @api.onchange("grid")
    def _apply_grid(self):
        """Reconcile the order's lines with the quantities entered in the grid.

        Lines are matched to a cell by their product variant, the same key used
        by lines otherwise added to the order, so the grid stays authoritative:
        setting a quantity updates the variant's line, zero removes it. A variant
        that ended up on several draft lines (one from the matrix and one added
        otherwise) is collapsed onto a single line; this is safe because the grid
        only runs while the order is a draft, when no move or allocation is
        attached to a line yet.
        """
        if not (self.grid and self.grid_update) or self.state != "draft":
            return
        grid = json.loads(self.grid)
        product_template = self.env["product.template"].browse(
            grid["product_template_id"]
        )
        Attrib = self.env["product.template.attribute.value"]
        new_lines = []
        for cell in grid["changes"]:
            combination = Attrib.browse(cell["ptav_ids"])
            product = product_template._create_product_variant(combination)
            request_lines = self.stock_request_ids.filtered(
                lambda line, product=product: (line._origin or line).product_id
                == product
            )
            old_qty = sum(request_lines.mapped("product_uom_qty"))
            qty = cell["qty"]
            if qty == old_qty:
                continue
            if not request_lines:
                new_lines.append(
                    Command.create(self._prepare_matrix_stock_request(product, qty))
                )
            elif qty == 0:
                self.stock_request_ids -= request_lines
            else:
                request_lines[0].product_uom_qty = qty
                self.stock_request_ids -= request_lines[1:]
        if new_lines:
            self.update({"stock_request_ids": new_lines})

    def _prepare_matrix_stock_request(self, product, qty):
        """Build the values for a stock request line created from the matrix.

        The order normally pushes its shared values down to its lines through
        ``change_childs``, which does not fire on matrix insertion, so the
        order-level required fields are added explicitly.
        """
        StockRequest = self.env["stock.request"]
        vals = StockRequest.default_get(list(StockRequest._fields))
        vals.update(
            {
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom_id": product.uom_id.id,
                "warehouse_id": self.warehouse_id.id,
                "location_id": self.location_id.id,
                "company_id": self.company_id.id,
                "expected_date": self.expected_date,
                "picking_policy": self.picking_policy,
                "requested_by": self.requested_by.id,
                "reference_ids": [Command.set(self.reference_ids.ids)],
            }
        )
        return vals

    def _get_matrix(self, product_template):
        """Return the template's variant grid, filled with the order's quantities.

        Each cell sums every request line holding that variant, however it was
        added to the order, so quantities already on the order show up.
        """
        self.ensure_one()

        def has_ptavs(line, sorted_attr_ids):
            ptav = (line._origin or line).product_template_attribute_value_ids.ids
            return sorted(ptav) == sorted_attr_ids

        matrix = product_template._get_template_matrix(company_id=self.company_id)
        if self.stock_request_ids:
            request_lines = self.stock_request_ids.filtered(
                lambda line: line.product_template_id == product_template
            )
            for row in matrix["matrix"]:
                for cell in row:
                    if cell.get("name", False):
                        continue
                    lines = request_lines.filtered(
                        lambda line, cell=cell: has_ptavs(line, cell["ptav_ids"])
                    )
                    if lines:
                        cell["qty"] = sum(lines.mapped("product_uom_qty"))
        return matrix
