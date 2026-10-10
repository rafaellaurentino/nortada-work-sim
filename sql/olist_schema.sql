-- Schema `nortada` = dataset público Olist (marketplace brasileiro), os "dados da empresa" na simulação.
-- Como usar (rodar com psql, porque \copy é um comando do psql):
--   1) createdb dw_nortada
--   2) baixe o dataset no Kaggle: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
--   3) coloque os CSVs em ./data/ (fora do Git, veja .gitignore)
--   4) psql -d dw_nortada -f sql/olist_schema.sql
--   Rode o psql na raiz do projeto para os caminhos data/... funcionarem.

CREATE SCHEMA IF NOT EXISTS nortada;

CREATE TABLE IF NOT EXISTS nortada.customers (
    customer_id              TEXT PRIMARY KEY,
    customer_unique_id       TEXT,
    customer_zip_code_prefix TEXT,
    customer_city            TEXT,
    customer_state           TEXT
);

CREATE TABLE IF NOT EXISTS nortada.orders (
    order_id                       TEXT PRIMARY KEY,
    customer_id                    TEXT,
    order_status                   TEXT,
    order_purchase_timestamp       TIMESTAMP,
    order_approved_at              TIMESTAMP,
    order_delivered_carrier_date   TIMESTAMP,
    order_delivered_customer_date  TIMESTAMP,
    order_estimated_delivery_date  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nortada.order_items (
    order_id            TEXT,
    order_item_id       INTEGER,
    product_id          TEXT,
    seller_id           TEXT,
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(12,2),
    freight_value       NUMERIC(12,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS nortada.order_payments (
    order_id             TEXT,
    payment_sequential   INTEGER,
    payment_type         TEXT,
    payment_installments INTEGER,
    payment_value        NUMERIC(12,2)
);

-- review_id NÃO é único nos dados originais; por isso sem chave primária (uma armadilha real!).
CREATE TABLE IF NOT EXISTS nortada.order_reviews (
    review_id               TEXT,
    order_id                TEXT,
    review_score            INTEGER,
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nortada.products (
    product_id                 TEXT PRIMARY KEY,
    product_category_name      TEXT,
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           INTEGER,
    product_length_cm          INTEGER,
    product_height_cm          INTEGER,
    product_width_cm           INTEGER
);

CREATE TABLE IF NOT EXISTS nortada.sellers (
    seller_id              TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT,
    seller_city            TEXT,
    seller_state           TEXT
);

CREATE TABLE IF NOT EXISTS nortada.geolocation (
    geolocation_zip_code_prefix TEXT,
    geolocation_lat             DOUBLE PRECISION,
    geolocation_lng             DOUBLE PRECISION,
    geolocation_city            TEXT,
    geolocation_state           TEXT
);

CREATE TABLE IF NOT EXISTS nortada.product_category_name_translation (
    product_category_name         TEXT PRIMARY KEY,
    product_category_name_english TEXT
);

-- Carga (ajuste os nomes dos arquivos se o seu download for diferente).
\copy nortada.customers FROM 'data/olist_customers_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.orders FROM 'data/olist_orders_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.order_items FROM 'data/olist_order_items_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.order_payments FROM 'data/olist_order_payments_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.order_reviews FROM 'data/olist_order_reviews_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.products FROM 'data/olist_products_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.sellers FROM 'data/olist_sellers_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.geolocation FROM 'data/olist_geolocation_dataset.csv' CSV HEADER ENCODING 'UTF8'
\copy nortada.product_category_name_translation FROM 'data/product_category_name_translation.csv' CSV HEADER ENCODING 'UTF8'

-- Conferência rápida (esperado: ~99 mil pedidos).
SELECT 'orders' AS tabela, COUNT(*) FROM nortada.orders
UNION ALL SELECT 'order_items', COUNT(*) FROM nortada.order_items
UNION ALL SELECT 'customers', COUNT(*) FROM nortada.customers;
