import frappe
from frappe.utils import get_link_to_form

def validate_donor_balance(self):
	donor_balance = sum([d.actual_balance for d in self.program_details])
	item_amount = sum([d.amount for d in self.items])

	if(not self.program_details):
		frappe.throw("Balance is required to proceed further.", title='Donor Balance')
	if(item_amount> donor_balance):
		frappe.throw("Item amount exceeding the available donor balance.", title='Items')

def get_company_defaults(self):
    temporary_project_fund_account = frappe.db.get_value("Company", self.company, "custom_default_temporary_project_fund_account")
    if(not temporary_project_fund_account):
        companylink = get_link_to_form("Company", self.company)
        frappe.throw(f""" Please set `Temporary Project Fund Account`. {companylink}""", title='Company')
    return temporary_project_fund_account

def make_funds_gl_entries(self):
    args = frappe._dict({
		'doctype': 'GL Entry',
		'posting_date': self.transaction_date,
		'transaction_date': self.transaction_date,
		'against': f"Material Request: {self.name}",
		'against_voucher_type': 'Material Request',
		'against_voucher': self.name,
		'voucher_type': 'Material Request',
		'voucher_no': self.name,
		'voucher_subtype': 'Receive',
		# 'remarks': self.instructions_internal,
		# 'is_opening': 'No',
		# 'is_advance': 'No',
		'company': self.company,
		# 'transaction_currency': self.currency,
		# 'transaction_exchange_rate': self.exchange_rate,
	})

def make_normal_equity_gl_entry():
    pass

def make_temporary_equity_gl_entry(self):
	def get_gl_args():
		return frappe._dict({
			'doctype': 'GL Entry',
			'account': get_company_defaults(self),
			'posting_date': self.transaction_date,
			'transaction_date': self.transaction_date,
			'against': f"Material Request: {self.name}",
			'against_voucher_type': 'Material Request',
			'against_voucher': self.name,
			'voucher_type': 'Material Request',
			'voucher_no': self.name,
			'voucher_subtype': 'Receive',
			# 'remarks': self.instructions_internal,
			# 'is_opening': 'No',
			# 'is_advance': 'No',
			'company': self.company,
			# 'transaction_currency': self.currency,
			# 'transaction_exchange_rate': self.exchange_rate,
		})
	args = get_gl_args()
	amount = sum([d.amount for d in self.items])
	for row in self.program_details:
		args.update({
			'party_type': 'Donor',
			'party': row.pd_donor,
			'cost_center': row.pd_cost_center,
			'service_area': row.pd_service_area,
			'subservice_area': row.pd_subservice_area,
			'product': row.pd_product,
			'project': row.pd_project,
			'donor': row.pd_donor,
			'credit': amount,
			'credit_in_account_currency': amount,
			'credit_in_transaction_currency': amount,
		})
		doc = frappe.get_doc(args)
		doc.insert(ignore_permissions=True)
		doc.submit()

def cancel_gl_entry(self):
    if(frappe.db.exists('GL Entry', {'against_voucher': self.name})):
        frappe.db.sql(f""" Delete from `tabGL Entry` where against_voucher = '{self.name}' """)
	