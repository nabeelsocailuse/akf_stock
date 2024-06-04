
frappe.ui.form.on("Stock Entry", {
    refresh: function(frm){
        toggle_fields(frm);
    },
    stock_entry_type: function(frm){
        toggle_fields(frm);
    }
});
frappe.ui.form.on("Stock Entry Detail", {
    custom_new: function(frm, cdt, cdn){
        let row = locals[cdt][cdn];
        if(row.custom_new){
            row.custom_used = 0;
        }
        frm.refresh_field("items")
    },
    custom_used: function(frm, cdt, cdn){
        let row = locals[cdt][cdn];
        if(row.custom_used){
            row.custom_new = 0;
        }
        frm.refresh_field("items")
    }
});

function toggle_fields(frm){
    if(frm.doc.stock_entry_type!="Donation"){
        frm.get_field("items").grid.toggle_display("custom_new", false);
        frm.get_field("items").grid.toggle_display("custom_used", false);
    }else{
        frm.get_field("items").grid.toggle_display("custom_new", true);
        frm.get_field("items").grid.toggle_display("custom_used", true);
    }
}
