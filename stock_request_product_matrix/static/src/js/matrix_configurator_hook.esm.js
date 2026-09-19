import {ProductMatrixDialog} from "@product_matrix/js/product_matrix_dialog";
import {useService} from "@web/core/utils/hooks";

export function useMatrixConfigurator() {
    const dialog = useService("dialog");

    const openDialog = (
        rootRecord,
        jsonInfo,
        productTemplateId,
        editedCellAttributes
    ) => {
        const infos = JSON.parse(jsonInfo);
        dialog.add(ProductMatrixDialog, {
            header: infos.header,
            rows: infos.matrix,
            editedCellAttributes: editedCellAttributes.toString(),
            product_template_id: productTemplateId,
            record: rootRecord,
        });
    };

    const open = async (record, edit) => {
        const rootRecord = record.model.root;

        // Fetch matrix information from server
        await rootRecord.update({
            grid_product_tmpl_id: record.data.product_template_id,
        });

        const updatedLineAttributes = [];
        if (edit) {
            // Provide attributes of the edited line to automatically focus on the
            // matching cell in the matrix
            for (const ptav of record.data.product_template_attribute_value_ids
                .records) {
                updatedLineAttributes.push(ptav.resId);
            }
            updatedLineAttributes.sort((a, b) => a - b);
        }

        openDialog(
            rootRecord,
            rootRecord.data.grid,
            record.data.product_template_id.id,
            updatedLineAttributes
        );

        if (!edit) {
            // Remove the temporary line used to open the matrix
            rootRecord.data.stock_request_ids.delete(record);
        }
    };

    return {open};
}
