# DB Schema

Generated from SQLAlchemy models and Alembic revision `20260512_0001`.

## users

- `id`: UUID primary key, default `gen_random_uuid()`
- `email`: string, unique, indexed, required
- `password_hash`: string, required
- `created_at`: timestamp with timezone, default `now()`

## user_profiles

- `user_id`: UUID primary key, foreign key to `users.id` with cascade delete
- `transport_mode`: string, required
- `diet_type`: string, required
- `housing_type`: string, required

## messages

- `id`: UUID primary key, default `gen_random_uuid()`
- `user_id`: UUID foreign key to `users.id` with cascade delete, indexed
- `role`: string, required
- `content`: text, required
- `carbon_gco2eq`: float, nullable
- `created_at`: timestamp with timezone, default `now()`

## daily_token_state

- Primary key: (`user_id`, `date`)
- `user_id`: UUID foreign key to `users.id` with cascade delete
- `date`: date, KST logical day
- `tokens_remaining`: float, default `150.0`
- `upload_reward_given`: float, default `0.0`
- `like_reward_given`: float, default `0.0`
- `total_reward_given`: float, default `0.0`
- `challenge_count`: integer, default `0`
- `updated_at`: timestamp with timezone, default `now()`

## token_transactions

- `id`: UUID primary key, default `gen_random_uuid()`
- `user_id`: UUID foreign key to `users.id` with cascade delete, indexed
- `daily_state_date`: date, linked with `user_id` to `daily_token_state`
- `type`: string, required
- `amount`: float, required
- `balance_after`: float, required
- `source_type`: string, nullable
- `source_id`: UUID, nullable
- `milestone`: integer, nullable
- `memo`: text, nullable
- `created_at`: timestamp with timezone, default `now()`
- Unique partial index: `uq_token_transactions_like_reward_milestone` on (`source_type`, `source_id`, `milestone`) where `type = 'like_reward'`

## challenges

- `id`: UUID primary key, default `gen_random_uuid()`
- `user_id`: UUID foreign key to `users.id` with cascade delete, indexed
- `category`: string, required
- `title`: string, required
- `description`: text, required
- `difficulty`: integer, required
- `status`: string, required
- `created_at`: timestamp with timezone, default `now()`
- `completed_at`: timestamp with timezone, nullable
- Unique partial index: `uq_challenges_one_open_per_user` on `user_id` where `status IN ('pending_acceptance', 'active')`

## challenge

- `id`: UUID primary key, default `gen_random_uuid()`
- `challenge_id`: UUID foreign key to `challenges.id` with cascade delete, unique
- `user_id`: UUID foreign key to `users.id` with cascade delete, indexed
- `file_path`: string, required
- `upload_rewarded`: boolean, default `false`
- `created_at`: timestamp with timezone, default `now()`

## likes

- `id`: UUID primary key, default `gen_random_uuid()`
- `photo_id`: UUID foreign key to `challenge_photos.id` with cascade delete, indexed
- `liker_user_id`: UUID foreign key to `users.id` with cascade delete, indexed
- `created_at`: timestamp with timezone, default `now()`
- Unique constraint: `uq_likes_photo_id_liker_user_id` on (`photo_id`, `liker_user_id`)
