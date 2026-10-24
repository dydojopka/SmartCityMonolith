PRAGMA foreign_keys=ON;

CREATE TABLE parkings (
	id VARCHAR(36) NOT NULL,
	name VARCHAR(200) NOT NULL,
	address VARCHAR(300) NOT NULL,
	latitude FLOAT NOT NULL,
	longitude FLOAT NOT NULL,
	total_spaces INTEGER NOT NULL,
	available_spaces INTEGER NOT NULL,
	price_per_hour_cents INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_parking_total CHECK (total_spaces >= 0),
	CONSTRAINT ck_parking_available CHECK (available_spaces >= 0 AND available_spaces <= total_spaces),
	CONSTRAINT ck_parking_price CHECK (price_per_hour_cents >= 0)
);

CREATE INDEX ix_parkings_available_spaces ON parkings (available_spaces);

CREATE TABLE vehicles (
	id VARCHAR(36) NOT NULL,
	type VARCHAR(30) NOT NULL,
	route_number VARCHAR(30) NOT NULL,
	plate_number VARCHAR(20),
	model VARCHAR(100),
	latitude FLOAT NOT NULL,
	longitude FLOAT NOT NULL,
	status VARCHAR(20) NOT NULL,
	updated_at DATETIME NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_vehicle_status CHECK (status IN ('ACTIVE','INACTIVE','MAINTENANCE'))
);

CREATE UNIQUE INDEX ix_vehicles_plate_number ON vehicles (plate_number);

CREATE INDEX ix_vehicles_status ON vehicles (status);

CREATE TABLE reservations (
	id VARCHAR(36) NOT NULL,
	parking_id VARCHAR(36) NOT NULL,
	user_id VARCHAR(36) NOT NULL,
	request_key VARCHAR(128),
	status VARCHAR(20) NOT NULL,
	created_at DATETIME NOT NULL,
	expires_at DATETIME,
	PRIMARY KEY (id),
	CONSTRAINT ck_reservation_status CHECK (status IN ('ACTIVE','CANCELLED','EXPIRED')),
	FOREIGN KEY(parking_id) REFERENCES parkings (id)
);

CREATE INDEX ix_reservations_parking_id ON reservations (parking_id);

CREATE INDEX ix_reservations_status ON reservations (status);

CREATE INDEX ix_reservations_user_id ON reservations (user_id);

CREATE UNIQUE INDEX uq_reservation_user_request ON reservations (user_id, request_key);
