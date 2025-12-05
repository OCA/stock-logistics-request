from . import models


def post_init_hook(env):
    """Set SQL defaults for required fields added by purchase_stock module.

    This is needed because purchase_stock (auto_install module) adds required fields
    to res.partner (group_rfq, group_on) but doesn't set SQL-level defaults.
    When tests or other code creates partners without explicitly setting these fields,
    the database constraint violation occurs even though Python-level defaults exist.
    """
    env.cr.execute("""
        ALTER TABLE res_partner
        ALTER COLUMN group_rfq SET DEFAULT 'default',
        ALTER COLUMN group_on SET DEFAULT 'default'
    """)
