PRAGMA foreign_keys=ON;

CREATE TABLE invoices (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	amount_cents INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	description VARCHAR(300),
	due_date DATE,
	paid_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_invoice_amount CHECK (typeof(amount_cents) = 'integer' AND amount_cents > 0),
	CONSTRAINT ck_invoice_status CHECK (status IN ('PENDING','PAID','CANCELLED'))
);

CREATE INDEX ix_invoices_status ON invoices (status);

CREATE INDEX ix_invoices_user_id ON invoices (user_id);

CREATE TABLE payments (
	id VARCHAR(36) NOT NULL,
	invoice_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	amount_cents INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	external_event_id VARCHAR(128),
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_payment_amount CHECK (typeof(amount_cents) = 'integer' AND amount_cents > 0),
	CONSTRAINT ck_payment_status CHECK (status IN ('CREATED','SUCCEEDED','FAILED')),
	FOREIGN KEY(invoice_id) REFERENCES invoices (id)
);

CREATE UNIQUE INDEX ix_payments_external_event_id ON payments (external_event_id);

CREATE UNIQUE INDEX ix_payments_idempotency_key ON payments (idempotency_key);

CREATE INDEX ix_payments_invoice_id ON payments (invoice_id);

CREATE INDEX ix_payments_status ON payments (status);

CREATE INDEX ix_payments_user_id ON payments (user_id);

CREATE UNIQUE INDEX uq_active_payment_invoice ON payments (invoice_id) WHERE status IN ('CREATED','SUCCEEDED');

CREATE TABLE webhook_events (
	id VARCHAR(36) NOT NULL,
	external_event_id VARCHAR(128) NOT NULL,
	payment_id VARCHAR(36) NOT NULL,
	event_type VARCHAR(50) NOT NULL,
	payload JSON,
	processed_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(payment_id) REFERENCES payments (id)
);

CREATE UNIQUE INDEX ix_webhook_events_external_event_id ON webhook_events (external_event_id);

CREATE INDEX ix_webhook_events_payment_id ON webhook_events (payment_id);
