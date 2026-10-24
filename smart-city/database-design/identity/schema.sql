PRAGMA foreign_keys=ON;

CREATE TABLE users (
	id VARCHAR(36) NOT NULL,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	first_name VARCHAR(100) NOT NULL,
	last_name VARCHAR(100) NOT NULL,
	role VARCHAR(20) NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_user_role CHECK (role IN ('USER','OPERATOR','ADMIN'))
);

CREATE UNIQUE INDEX ix_users_email ON users (email);
