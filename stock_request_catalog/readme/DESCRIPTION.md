This module brings Odoo's product **Catalog** to stock request orders, the same
way it works on sale orders:

- Adds a *Catalog* button to the request lines of a stock request order.
- Opens the standard product catalog (kanban) where products can be added,
  removed and re-quantified with the +/- controls.
- Turns the catalog selection into stock request lines when going back to the
  order, one line per product, each inheriting the order's warehouse, location,
  company and scheduling.

It reuses Odoo's core `product.catalog.mixin`. As stock requests have no price, the catalog shows on-hand
stock per product instead of a monetary amount.
