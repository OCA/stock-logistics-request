This module applies to configurable products, i.e. product templates that
have attribute lines generating several variants. Make sure such a product
exists before using the grid.

To use this module:

1.  Go to *Inventory > Operations > Stock Requests > Stock Request Orders*
    and create a new order.
2.  Set the warehouse and location (and any other order-level values); the
    lines inherit them.
3.  On a request line, choose a configurable product in the *Product* column.
    - If the product has a single variant, that variant is set directly on
      the line.
    - If it has several variants, a matrix of the variants opens.
4.  Enter the quantities per variant in the matrix and confirm.
5.  One request line is created per variant with a non-zero quantity. Use the
    pencil button next to the product to reopen the matrix and adjust the
    quantities.
