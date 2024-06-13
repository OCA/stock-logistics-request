import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-stock-logistics-request",
    description="Meta package for oca-stock-logistics-request Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-stock_request>=16.0dev,<16.1dev',
        'odoo-addon-stock_request_direction>=16.0dev,<16.1dev',
        'odoo-addon-stock_request_mrp>=16.0dev,<16.1dev',
        'odoo-addon-stock_request_picking_type>=16.0dev,<16.1dev',
        'odoo-addon-stock_request_purchase>=16.0dev,<16.1dev',
        'odoo-addon-stock_request_submit>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
