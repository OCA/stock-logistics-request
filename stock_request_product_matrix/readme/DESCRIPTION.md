This module adds a grid entry (matrix) to stock request orders, letting
users request many variants of a configurable product at once instead of
adding one stock request line per variant by hand.

When a configurable product template is selected on a stock request order
line, a matrix of its variants opens. The quantities entered in the matrix
are turned into stock request lines, one line per variant with a non-zero
quantity, each inheriting the order's warehouse, location, company and
scheduling. It reuses the standard Odoo `product_matrix` grid, trimmed down
to what stock requests need (no pricing).

**Known limitations**

- Only real, stored variants are handled. Attributes configured to *not*
  create variants ("no variant" / dynamically created variants) are ignored
  by the grid.
- The matrix is a data-entry convenience only; it is not rendered on any
  stock request report.
- When a variant is spread over several draft request lines, editing its
  quantity in the grid keeps a single line and drops the extras.

**Related modules**

- `stock_request_catalog` adds a product catalog to stock request orders; it
  works well together with this module, and lines it adds are reconciled by the
  grid like any other.
