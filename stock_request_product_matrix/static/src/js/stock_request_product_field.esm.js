import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {
    Many2OneField,
    buildM2OFieldDescription,
} from "@web/views/fields/many2one/many2one_field";
import {useMatrixConfigurator} from "@stock_request_product_matrix/js/matrix_configurator_hook.esm";

export class StockRequestProductField extends Many2OneField {
    static template = "stock_request_product_matrix.StockRequestProductField";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.matrixConfigurator = useMatrixConfigurator();
    }

    get relation() {
        return this.props.record.fields[this.props.name].relation;
    }

    get isTemplateField() {
        return this.relation === "product.template";
    }

    get configurationButtonHelp() {
        return _t("Edit Configuration");
    }

    get isConfigurableTemplate() {
        return this.props.record.data.is_configurable_product;
    }

    get hasVariant() {
        return Boolean(this.props.record.data.product_id);
    }

    get orderInDraft() {
        return this.props.record.model.root.data.state === "draft";
    }

    get m2oProps() {
        const props = super.m2oProps;
        if (!this.isTemplateField) {
            return props;
        }
        const variant = this.props.record.data.product_id;
        return {
            ...props,
            // Show the selected variant's name in the template column so the user
            // can tell which variant the line holds.
            value:
                variant && props.value
                    ? {...props.value, display_name: variant.display_name}
                    : props.value,
            // Resolve the template right after it is picked (single variant -> set
            // the variant; several variants -> open the matrix). Doing it here,
            // rather than through a record observer, guarantees it fires on the
            // user's selection and not on later recomputes.
            update: async (value, options) => {
                await props.update(value, options);
                if (this.props.record.data.product_template_id?.id) {
                    await this._onProductTemplateUpdate();
                }
            },
        };
    }

    async _onProductTemplateUpdate() {
        const result = await this.orm.call(
            "product.template",
            "get_single_product_variant",
            [this.props.record.data.product_template_id.id]
        );
        if (result && result.product_id) {
            if (this.props.record.data.product_id != result.product_id.id) {
                this.props.record.update({
                    product_id: {
                        id: result.product_id,
                        display_name: result.product_name,
                    },
                });
            }
        } else {
            this.matrixConfigurator.open(this.props.record, false);
        }
    }

    onEditConfiguration() {
        if (this.isConfigurableTemplate && this.orderInDraft) {
            this.matrixConfigurator.open(this.props.record, true);
        }
    }
}

registry.category("fields").add("stock_request_product_many2one", {
    ...buildM2OFieldDescription(StockRequestProductField),
    fieldDependencies: [
        {name: "is_configurable_product", type: "boolean"},
        {name: "product_template_attribute_value_ids", type: "many2many"},
    ],
});
