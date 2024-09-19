from openupgradelib.openupgrade_160 import fill_analytic_distribution

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Migrate stock_request's analytic account and tags
    if table_exists(cr, "account_analytic_distribution"):  # 16.0
        fill_analytic_distribution(
            env,
            "stock_request",
            "account_analytic_tag_stock_request_rel",
            "stock_request_id",
        )
    else:  # 17.0, analytic account only
        cr.execute(
            """
            update stock_request set analytic_distribution =
            json_build_object(analytic_account_id::varchar, 100.0)
            where analytic_account_id is not null;
            """
        )
    # Migrate stock_request_order's analytic account
    cr.execute(
        """
        update stock_request_order set analytic_distribution =
        json_build_object(default_analytic_account_id::varchar, 100.0)
        where default_analytic_account_id is not null;
        """
    )
