# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_copy_allocation_vals(self, vals):
        # The split of a production allocates its backorders afterwards
        if self.env.context.get("skip_production_allocation_copy") and (
            self.production_id
        ):
            return []
        return super()._prepare_copy_allocation_vals(vals)
