PRAGMA foreign_keys=ON;

CREATE TABLE issues (
	id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	request_key VARCHAR(128),
	title VARCHAR(200) NOT NULL,
	description TEXT NOT NULL,
	category VARCHAR(50) NOT NULL,
	address VARCHAR(300) NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_issue_status CHECK (status IN ('NEW','IN_PROGRESS','RESOLVED','REJECTED'))
);

CREATE INDEX ix_issues_category ON issues (category);

CREATE INDEX ix_issues_status ON issues (status);

CREATE INDEX ix_issues_user_id ON issues (user_id);

CREATE UNIQUE INDEX uq_issue_user_request ON issues (user_id, request_key);
