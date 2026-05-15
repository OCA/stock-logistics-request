There is no way to achieve Storck Request and Stock Request Orders. It
should be developed taking into account that only Cancel and Done stock
request can be archived.

It is also required to manage active field logically from Orders to SRs.

In case of multi step routes, the stock_request_id is not propagated in the downstream moves as this will then create a link / allocation to all moves in the chain. This however prevents linking other related documents (PO - stock_request_purchase, MO - stock_request_mrp) when they are generated at the end of the procurement chain. TODO: investigate propagating the value in the context instead and use this additionally to the one passed in the procurement values when generating the MO (stock_request_mrp) / PO (stock_request_purchase).
