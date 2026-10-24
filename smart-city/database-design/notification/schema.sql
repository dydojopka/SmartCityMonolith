PRAGMA foreign_keys=ON;

CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36),
	recipient VARCHAR(255) NOT NULL,
	channel VARCHAR(50) NOT NULL,
	subject VARCHAR(255),
	message TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at DATETIME NOT NULL,
	sent_at DATETIME,
	PRIMARY KEY (id),
	CONSTRAINT ck_notification_status CHECK (status IN ('PENDING','SENT','FAILED')),
	CONSTRAINT ck_notification_channel CHECK (channel IN ('EMAIL','SMS','PUSH'))
);

CREATE INDEX ix_notifications_created_at ON notifications (created_at);

CREATE INDEX ix_notifications_status ON notifications (status);
