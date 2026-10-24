PRAGMA foreign_keys=ON;

CREATE TABLE sensors (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(255) NOT NULL,
	type VARCHAR(100) NOT NULL,
	location VARCHAR(255),
	unit VARCHAR(50) NOT NULL,
	latitude FLOAT NOT NULL,
	longitude FLOAT NOT NULL,
	api_key_hash VARCHAR(64) NOT NULL,
	status VARCHAR(20) NOT NULL,
	last_seen_at DATETIME,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_sensor_status CHECK (status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE sensor_readings (
	id VARCHAR(36) NOT NULL,
	sensor_id VARCHAR(36) NOT NULL,
	value FLOAT NOT NULL,
	unit VARCHAR(50),
	measured_at DATETIME NOT NULL,
	received_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(sensor_id) REFERENCES sensors (id) ON DELETE CASCADE
);

CREATE INDEX ix_sensor_readings_sensor_id_measured_at ON sensor_readings (sensor_id, measured_at);
