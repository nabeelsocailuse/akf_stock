frappe.ui.form.on("Stock Entry", {
  refresh: function (frm) {
    set_queries(frm);
    set_inventory_flag(frm);

    if (frm.doc.docstatus === 1) {
      if (frm.doc.add_to_transit && frm.doc.purpose == 'Material Transfer' && frm.doc.per_transferred < 100) {
        frm.add_custom_button(__('Lost / Wastage'), function () {
          frappe.model.open_mapped_doc({
            method: "akf_stock.customization.extends.custom_stock_entry.make_stock_in_lost_entry",
            frm: frm
          })
        });
      }
    }
  },
  // Below code is added by Mubashir Bashir
  // ////////////////////START/////////////////////////
  onload: function (frm) {
    frm.original_qty_values = {};
    frm.doc.items.forEach(function (item) {
      if (item.material_request) {
        frm.original_qty_values[item.name] = item.qty;
      }
    });
  },
  validate: function (frm) {
    frm.doc.items.forEach(function (item) {
      if (item.material_request) {
        var original_qty = frm.original_qty_values[item.name];

        if (item.qty > original_qty) {
          frappe.throw(`The quantity for item ${item.item_code} cannot exceed ${original_qty}`);
        }
      }
    });
  },
  // ////////////////////END/////////////////////////
  stock_entry_type: function (frm) {
    set_inventory_flag(frm);

    if (frm.doc.stock_entry_type == "Donated Inventory Receive - Restricted" || frm.doc.stock_entry_type == "Donated Inventory Disposal - Restricted") {
      (frm.doc.items || []).forEach((item) => {
        frappe.model.set_value(
          "Stock Entry Detail",
          item.name,
          "inventory_flag",
          "Donated"
        );

        frappe.model.set_value(
          "Stock Entry Detail",
          item.name,
          "inventory_scenario",
          "Restricted"
        );
      });
      frm.get_field("items").grid.toggle_display("inventory_flag", false);
      frm.get_field("items").grid.toggle_display("inventory_scenario", false);
    } else {
      frm.get_field("items").grid.toggle_display("inventory_flag", true);
      frm.get_field("items").grid.toggle_display("inventory_scenario", true);
    }
  },
});

frappe.ui.form.on("Stock Entry Detail", {
  custom_new: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.custom_new) {
      row.custom_used = 0;
    }
    frm.refresh_field("items")
    set_queries(frm);
  },
  custom_used: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.custom_used) {
      row.custom_new = 0;
    }
    frm.refresh_field("items")
    set_queries(frm);
  },
  program: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.program) {
      row.subservice_area = "";
      row.product = "";
      row.project = "";
    }
    frm.refresh_field("items")
    set_queries(frm);
  },
  subservice_area: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.program) {
      row.product = "";
      row.project = "";
    }
    frm.refresh_field("items")
    set_queries(frm);
  },
  product: function (frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (row.program) {
      row.project = "";
    }
    frm.refresh_field("items")
    set_queries(frm);
  },
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

function set_inventory_flag(frm) {
  if ((frm.doc.stock_entry_type == "Donated Inventory Receive - Restricted") || (frm.doc.stock_entry_type == "Donated Inventory Disposal - Restricted")) {
    (frm.doc.items || []).forEach((item) => {
      frappe.model.set_value(
        "Stock Entry Detail",
        item.name,
        "inventory_flag",
        "Donated"
      );

      frappe.model.set_value(
        "Stock Entry Detail",
        item.name,
        "inventory_scenario",
        "Restricted"
      );
    });
    frm.get_field("items").grid.toggle_display("inventory_flag", false);
    frm.get_field("items").grid.toggle_display("inventory_scenario", false);
  } else {
    frm.get_field("items").grid.toggle_display("inventory_flag", true);
    frm.get_field("items").grid.toggle_display("inventory_scenario", true);
  }

  if (frm.doc.purpose != "Material Issue") {
    frm.get_field("items").grid.toggle_display("custom_target_project", true);
  }
  else {
    frm.get_field("items").grid.toggle_display("custom_target_project", false);
  }
}

