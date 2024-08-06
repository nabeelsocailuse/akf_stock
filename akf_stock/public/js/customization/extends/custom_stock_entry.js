
frappe.ui.form.on("Stock Entry", {
    stock_entry_type: function (frm, cdt, cdn) {
        if (
          frm.doc.stock_entry_type == "Donation" ||
          frm.doc.stock_entry_type == "Donated Inventory Consumption" ||
          frm.doc.stock_entry_type == "Donated Inventory Transfer"
        ) {
          (frm.doc.items || []).forEach((item) => {
            frappe.model.set_value(
              "Stock Entry Detail",
              item.name,
              "inventory_flag",
              "Donated"
            );
          });
        } else {
          (frm.doc.items || []).forEach((item) => {
            frappe.model.set_value(
              "Stock Entry Detail",
              item.name,
              "inventory_flag",
              "Purchased"
            );
          });
        }
      },
    refresh: function(frm){
      set_queries(frm);
        // toggle_fields(frm);
    },
//     stock_entry_type: function(frm){
//         toggle_fields(frm);
//     }
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

function set_queries(frm) {
  frm.fields_dict["items"].grid.get_field("subservice_area").get_query =
    function (doc, cdt, cdn) {
      let row = locals[cdt][cdn];
      return {
        filters: {
          service_area: row.program,
        },
      };
    };

  frm.fields_dict["items"].grid.get_field("product").get_query = function (
    doc,
    cdt,
    cdn
  ) {
    let row = locals[cdt][cdn];
    return {
      filters: {
        subservice_area: row.subservice_area,
      },
    };
  };

  frm.fields_dict["items"].grid.get_field("project").get_query = function (
    doc,
    cdt,
    cdn
  ) {
    let row = locals[cdt][cdn];
    return {
      filters: {
        custom_program: row.program,
      },
    };
  };
}

// function toggle_fields(frm){
//     if(frm.doc.stock_entry_type!="Donation"){
//         frm.get_field("items").grid.toggle_display("custom_new", false);
//         frm.get_field("items").grid.toggle_display("custom_used", false);
//     }else{
//         frm.get_field("items").grid.toggle_display("custom_new", true);
//         frm.get_field("items").grid.toggle_display("custom_used", true);
//     }
// }
