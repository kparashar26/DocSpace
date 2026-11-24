--
-- PostgreSQL database dump
--

\restrict LtO9eAZDHfLssE8MFtcGCMNzdmC6Rfl9uGydjbhK52vTbcHVD0cKFHdyJcjZs1q

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: document_source_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE "public"."document_source_type" AS ENUM (
    'upload',
    'google_drive'
);


--
-- Name: document_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE "public"."document_status" AS ENUM (
    'pending',
    'processing',
    'ready',
    'failed'
);


--
-- Name: message_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE "public"."message_role" AS ENUM (
    'user',
    'assistant'
);


SET default_tablespace = '';

SET default_table_access_method = "heap";

--
-- Name: chat_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."chat_conversations" (
    "id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "document_id" "uuid",
    "title" character varying(200),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."chat_messages" (
    "id" "uuid" NOT NULL,
    "conversation_id" "uuid" NOT NULL,
    "role" "public"."message_role" NOT NULL,
    "content" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: document_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."document_chunks" (
    "id" "uuid" NOT NULL,
    "document_id" "uuid" NOT NULL,
    "chunk_index" integer NOT NULL,
    "page_start" integer,
    "page_end" integer,
    "content" "text" NOT NULL
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."documents" (
    "id" "uuid" NOT NULL,
    "workspace_id" "uuid",
    "user_id" "uuid",
    "filename" character varying(255) NOT NULL,
    "source_type" "public"."document_source_type" NOT NULL,
    "source_file_id" "text",
    "storage_key" "text",
    "mime_type" character varying(100) NOT NULL,
    "file_size_bytes" bigint,
    "status" "public"."document_status" DEFAULT 'pending'::"public"."document_status" NOT NULL,
    "page_count" integer,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: message_citations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."message_citations" (
    "id" "uuid" NOT NULL,
    "message_id" "uuid" NOT NULL,
    "chunk_id" "uuid" NOT NULL
);


--
-- Name: permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."permissions" (
    "id" "uuid" NOT NULL,
    "name" character varying(100) NOT NULL,
    "code" character varying(100) NOT NULL,
    "description" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."role_permissions" (
    "role_id" "uuid" NOT NULL,
    "permission_id" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."roles" (
    "id" "uuid" NOT NULL,
    "name" character varying(50) NOT NULL,
    "description" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."users" (
    "id" "uuid" NOT NULL,
    "name" character varying(100) NOT NULL,
    "email" character varying(255) NOT NULL,
    "password_hash" "text" NOT NULL,
    "role_id" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Name: workspaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."workspaces" (
    "id" "uuid" NOT NULL,
    "name" character varying(100) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


--
-- Data for Name: chat_conversations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."chat_conversations" ("id", "user_id", "document_id", "title", "created_at", "updated_at") FROM stdin;
\.


--
-- Data for Name: chat_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."chat_messages" ("id", "conversation_id", "role", "content", "created_at") FROM stdin;
\.


--
-- Data for Name: document_chunks; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."document_chunks" ("id", "document_id", "chunk_index", "page_start", "page_end", "content") FROM stdin;
699dcc97-660c-48d3-ab53-1f303b24fafb	147a8631-2d8a-4418-88c7-e6dab413c0ca	0	1	1	Round 1 Question Sets – Technical Intern Hiring \nQuestion \nSkill \nSuggested time \nMarks \nQ1 Easy coding \nArrays, strings, basic \nlogic \n15 min \n30 \nQ2 Medium coding \nStack, sliding window, \nDP, 2D arrays \n30 min \n45 \nQ3 Debugging \nReading code, edge \ncases \n15 min \n25 \nRules for candidates: any language for Q1 and Q2; Q3 is given in Python, Java and C++, pick one. Full \nscreen shared and camera on throughout. No AI tools, no web search; the IDE's own docs are allowed. \nSubmit code through the form before time ends. \nSet 1 \nQ1 (Easy): Question-mark pairs \nA string contains digits, letters and ?. Look at each pair of consecutive digits (letters and ? between them \ndon't break the pair). Count the pairs whose digits add up to 10 and have exactly three ? between them. \nExample: "arrb6???4xxbl5???eee5" → 2 (6 and 4, then 5 and 5) \nInput \nExpected \n"arrb6???4xxbl5???eee5" \n2 \n"acc?7??sss?3rr1??????5" \n1 \n"5??aaaaaaaaaaaaaaaaaaa?5?5" \n1 \n"9???1???9???1" \n3 \n"aa6?9" \n0 \n"1???9" \n1 \nQ2
1c1e6a41-634b-4fe3-9154-62c42a8b8d77	147a8631-2d8a-4418-88c7-e6dab413c0ca	1	1	1	ut \nExpected \n"arrb6???4xxbl5???eee5" \n2 \n"acc?7??sss?3rr1??????5" \n1 \n"5??aaaaaaaaaaaaaaaaaaa?5?5" \n1 \n"9???1???9???1" \n3 \n"aa6?9" \n0 \n"1???9" \n1 \nQ2 (Medium): Longest stretch with k letters \nGiven a string and a number k, return the longest substring that uses at most k different characters. If \ntwo are equally long, return the one that starts first. \nExample: "aabbcbbbadef", k = 2 → "bbcbbb" \nInput \nk \nExpected \n"aabbcbbbadef" \n2 \n"bbcbbb"
9c26d310-7b10-41b7-8c95-4a11b4449150	147a8631-2d8a-4418-88c7-e6dab413c0ca	2	2	2	Input \nk \nExpected \n"abc" \n1 \n"a" \n"aaaa" \n2 \n"aaaa" \n"" \n3 \n"" \n"eceba" \n2 \n"ece" \n"abaccc" \n2 \n"accc" \nQ3 (Debugging): Binary search \nThe function should return the index of target in a sorted list, or -1 if it is absent. It sometimes misses \nthe target and sometimes never finishes. Find and fix the bugs. \nPython \ndef binary_search(arr, target): \n    lo, hi = 0, len(arr) - 1 \n    while lo < hi: \n        mid = (lo + hi) // 2 \n        if arr[mid] == target: \n            return mid \n        elif arr[mid] < target: \n            lo = mid \n        else: \n            hi = mid - 1 \n    return -1 \n OR Java \nstatic int binarySearch(int[] arr, int target) { \n    int lo = 0, hi = arr.length - 1; \n    while (lo < hi) { \n        int mid = (lo + hi) / 2; \n        if (arr[mid] == target) return mid; \n        else if (arr[mid] < target) lo = mid; \n        else hi = mid - 1; \n    } \n    return -1; \n} \nOR C++ \nint binarySearch(const std::vector<int>& arr, int target) { \n    int lo = 0, hi =
d3f5cad6-b5e9-4ba0-86d1-79233a4838bf	147a8631-2d8a-4418-88c7-e6dab413c0ca	3	2	2	mid; \n        else hi = mid - 1; \n    } \n    return -1; \n} \nOR C++ \nint binarySearch(const std::vector<int>& arr, int target) { \n    int lo = 0, hi = static_cast<int>(arr.size()) - 1; \n    while (lo < hi) { \n        int mid = (lo + hi) / 2; \n        if (arr[mid] == target) return mid; \n        else if (arr[mid] < target) lo = mid; \n        else hi = mid - 1; \n    } \n    return -1; \n}
62cc512a-ecd5-477b-a5fc-65af259d4a4b	147a8631-2d8a-4418-88c7-e6dab413c0ca	4	3	3	Input \nTarget \nExpected after fix \n[5] \n5 \n0 \n[1, 3] \n3 \n1 \n[1, 3, 5, 7, 9] \n7 \n3 \n[1, 3, 5, 7, 9] \n4 \n-1 \n[] \n1 \n-1
\.


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."documents" ("id", "workspace_id", "user_id", "filename", "source_type", "source_file_id", "storage_key", "mime_type", "file_size_bytes", "status", "page_count", "created_at", "updated_at") FROM stdin;
147a8631-2d8a-4418-88c7-e6dab413c0ca	\N	73c4b87b-3ce2-4d56-a01c-0f150bbb4ba7	Round1_Question_Sets (3) - with CPP (1).pdf	upload	\N	uploads/cff7ef6ad4d845f7a538a612de863f77.pdf	application/pdf	183259	ready	3	2026-11-13 10:23:53.545557+05:30	2026-11-13 10:23:53.593225+05:30
\.


--
-- Data for Name: message_citations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."message_citations" ("id", "message_id", "chunk_id") FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."permissions" ("id", "name", "code", "description", "created_at") FROM stdin;
71f04270-c0a6-42cd-969f-a633b2343d6c	Manage Users	users.manage	Create, update and manage users	2026-11-10 10:44:17.332515+05:30
d4ad0810-d2bf-4bc3-942b-80f92962fceb	Manage Roles	roles.manage	Manage application roles	2026-11-10 10:44:17.332515+05:30
e0055a1d-1f1f-481f-848d-4b34b28e6660	Manage Permissions	permissions.manage	Manage role permissions	2026-11-10 10:44:17.332515+05:30
c9a32fcd-20eb-4fcb-bfe1-8eb2422c941b	Upload Documents	documents.upload	Upload documents	2026-11-10 10:44:17.332515+05:30
e926a031-f8e3-4dd4-86fc-ec482625314d	View Documents	documents.view	View documents	2026-11-10 10:44:17.332515+05:30
e41912d3-202b-42e8-9dac-eb5717e10a00	Update Documents	documents.update	Update documents	2026-11-10 10:44:17.332515+05:30
4923437d-3995-440f-a6ac-7c2f0be70925	Delete Documents	documents.delete	Delete documents	2026-11-10 10:44:17.332515+05:30
0205a67d-cdc0-4736-bd54-83caefa9d154	Manage Workspaces	workspaces.manage	Manage document categories	2026-11-10 10:44:17.332515+05:30
af4010fe-25bb-4fee-830f-829c6b122c07	Use Chat	chat.use	Use document chat	2026-11-10 10:44:17.332515+05:30
\.


--
-- Data for Name: role_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."role_permissions" ("role_id", "permission_id", "created_at") FROM stdin;
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	71f04270-c0a6-42cd-969f-a633b2343d6c	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	d4ad0810-d2bf-4bc3-942b-80f92962fceb	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	e0055a1d-1f1f-481f-848d-4b34b28e6660	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	c9a32fcd-20eb-4fcb-bfe1-8eb2422c941b	2026-11-10 10:52:24.824872+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	c9a32fcd-20eb-4fcb-bfe1-8eb2422c941b	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	e926a031-f8e3-4dd4-86fc-ec482625314d	2026-11-10 10:52:24.824872+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	e926a031-f8e3-4dd4-86fc-ec482625314d	2026-11-10 10:52:24.824872+05:30
bc5c2e54-651a-4088-9998-de8238a5e765	e926a031-f8e3-4dd4-86fc-ec482625314d	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	e41912d3-202b-42e8-9dac-eb5717e10a00	2026-11-10 10:52:24.824872+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	e41912d3-202b-42e8-9dac-eb5717e10a00	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	4923437d-3995-440f-a6ac-7c2f0be70925	2026-11-10 10:52:24.824872+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	4923437d-3995-440f-a6ac-7c2f0be70925	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	0205a67d-cdc0-4736-bd54-83caefa9d154	2026-11-10 10:52:24.824872+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	0205a67d-cdc0-4736-bd54-83caefa9d154	2026-11-10 10:52:24.824872+05:30
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	af4010fe-25bb-4fee-830f-829c6b122c07	2026-11-10 10:52:24.824872+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	af4010fe-25bb-4fee-830f-829c6b122c07	2026-11-10 10:52:24.824872+05:30
bc5c2e54-651a-4088-9998-de8238a5e765	af4010fe-25bb-4fee-830f-829c6b122c07	2026-11-10 10:52:24.824872+05:30
\.


--
-- Data for Name: roles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."roles" ("id", "name", "description", "created_at", "updated_at") FROM stdin;
a7b6eb40-7d43-4915-b71c-7be7f6f40c55	admin	Full administrative access	2026-11-10 10:37:28.076516+05:30	2026-11-10 10:37:28.076516+05:30
1875599a-2fa9-4f2b-8189-75c05ae31b73	editor	Manage documents and content	2026-11-10 10:37:28.076516+05:30	2026-11-10 10:37:28.076516+05:30
bc5c2e54-651a-4088-9998-de8238a5e765	viewer	View documents and permitted content	2026-11-10 10:37:28.076516+05:30	2026-11-10 10:37:28.076516+05:30
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."users" ("id", "name", "email", "password_hash", "role_id", "created_at", "updated_at") FROM stdin;
bf6f892b-3e6a-46cd-a608-f25848da79c2	Shri	shri@example.com	$argon2id$v=19$m=65536,t=3,p=4$AHuU+Zntm65YvzVZ0+4ntQ$fnAyOPXorwCrMYGYmUvY2/9/s9A/B/0kpFPiW3FKtQI	bc5c2e54-651a-4088-9998-de8238a5e765	2026-11-10 11:48:06.888825+05:30	2026-11-10 11:48:06.888825+05:30
90f65658-ff11-4df6-828a-fa23263ad00f	Shri	shri@gmail.com	$argon2id$v=19$m=65536,t=3,p=4$vz2psISFDy95RdkUGiG1Vg$LILVI1T8/s+SWqaJh6PI/dbR2zRSxdBh7+m1Tr+O+qU	bc5c2e54-651a-4088-9998-de8238a5e765	2026-11-10 11:48:27.099417+05:30	2026-11-10 11:48:27.099417+05:30
73c4b87b-3ce2-4d56-a01c-0f150bbb4ba7	shrinath	shrinath@example.com	$argon2id$v=19$m=65536,t=3,p=4$yWQR3hw7igJx6Bd+gm2ZCQ$uGpJiVYlFrvGR649MfRlKYpkniS2yD63BMuNvSwKNBA	a7b6eb40-7d43-4915-b71c-7be7f6f40c55	2026-11-12 15:54:04.945127+05:30	2026-11-13 10:18:19.170012+05:30
\.


--
-- Data for Name: workspaces; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."workspaces" ("id", "name", "created_at", "updated_at") FROM stdin;
\.


--
-- Name: chat_conversations chat_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."chat_conversations"
    ADD CONSTRAINT "chat_conversations_pkey" PRIMARY KEY ("id");


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."chat_messages"
    ADD CONSTRAINT "chat_messages_pkey" PRIMARY KEY ("id");


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."document_chunks"
    ADD CONSTRAINT "document_chunks_pkey" PRIMARY KEY ("id");


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id");


--
-- Name: message_citations message_citations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."message_citations"
    ADD CONSTRAINT "message_citations_pkey" PRIMARY KEY ("id");


--
-- Name: permissions permissions_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."permissions"
    ADD CONSTRAINT "permissions_code_key" UNIQUE ("code");


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."permissions"
    ADD CONSTRAINT "permissions_pkey" PRIMARY KEY ("id");


--
-- Name: role_permissions pk_role_permissions; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."role_permissions"
    ADD CONSTRAINT "pk_role_permissions" PRIMARY KEY ("role_id", "permission_id");


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."roles"
    ADD CONSTRAINT "roles_name_key" UNIQUE ("name");


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."roles"
    ADD CONSTRAINT "roles_pkey" PRIMARY KEY ("id");


--
-- Name: document_chunks uq_document_chunk_index; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."document_chunks"
    ADD CONSTRAINT "uq_document_chunk_index" UNIQUE ("document_id", "chunk_index");


--
-- Name: documents uq_document_source; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "uq_document_source" UNIQUE ("source_type", "source_file_id");


--
-- Name: message_citations uq_message_chunk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."message_citations"
    ADD CONSTRAINT "uq_message_chunk" UNIQUE ("message_id", "chunk_id");


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_email_key" UNIQUE ("email");


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");


--
-- Name: workspaces workspaces_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."workspaces"
    ADD CONSTRAINT "workspaces_name_key" UNIQUE ("name");


--
-- Name: workspaces workspaces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."workspaces"
    ADD CONSTRAINT "workspaces_pkey" PRIMARY KEY ("id");


--
-- Name: idx_chat_conversations_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_chat_conversations_document_id" ON "public"."chat_conversations" USING "btree" ("document_id");


--
-- Name: idx_chat_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_chat_conversations_user_id" ON "public"."chat_conversations" USING "btree" ("user_id");


--
-- Name: idx_chat_messages_conversation_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_chat_messages_conversation_created" ON "public"."chat_messages" USING "btree" ("conversation_id", "created_at");


--
-- Name: idx_documents_uploaded_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_documents_uploaded_by" ON "public"."documents" USING "btree" ("user_id");


--
-- Name: idx_documents_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_documents_workspace_id" ON "public"."documents" USING "btree" ("workspace_id");


--
-- Name: idx_message_citations_chunk_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_message_citations_chunk_id" ON "public"."message_citations" USING "btree" ("chunk_id");


--
-- Name: idx_users_role_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "idx_users_role_id" ON "public"."users" USING "btree" ("role_id");


--
-- Name: chat_conversations fk_chat_conversations_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."chat_conversations"
    ADD CONSTRAINT "fk_chat_conversations_document" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE SET NULL;


--
-- Name: chat_conversations fk_chat_conversations_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."chat_conversations"
    ADD CONSTRAINT "fk_chat_conversations_user" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;


--
-- Name: chat_messages fk_chat_messages_conversation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."chat_messages"
    ADD CONSTRAINT "fk_chat_messages_conversation" FOREIGN KEY ("conversation_id") REFERENCES "public"."chat_conversations"("id") ON DELETE CASCADE;


--
-- Name: document_chunks fk_document_chunks_document; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."document_chunks"
    ADD CONSTRAINT "fk_document_chunks_document" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE CASCADE;


--
-- Name: documents fk_documents_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "fk_documents_user" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE SET NULL;


--
-- Name: documents fk_documents_workspace; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "fk_documents_workspace" FOREIGN KEY ("workspace_id") REFERENCES "public"."workspaces"("id") ON DELETE SET NULL;


--
-- Name: message_citations fk_message_citations_chunk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."message_citations"
    ADD CONSTRAINT "fk_message_citations_chunk" FOREIGN KEY ("chunk_id") REFERENCES "public"."document_chunks"("id") ON DELETE CASCADE;


--
-- Name: message_citations fk_message_citations_message; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."message_citations"
    ADD CONSTRAINT "fk_message_citations_message" FOREIGN KEY ("message_id") REFERENCES "public"."chat_messages"("id") ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_permission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."role_permissions"
    ADD CONSTRAINT "fk_role_permissions_permission" FOREIGN KEY ("permission_id") REFERENCES "public"."permissions"("id") ON DELETE CASCADE;


--
-- Name: role_permissions fk_role_permissions_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."role_permissions"
    ADD CONSTRAINT "fk_role_permissions_role" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE CASCADE;


--
-- Name: users fk_users_role; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "fk_users_role" FOREIGN KEY ("role_id") REFERENCES "public"."roles"("id") ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict LtO9eAZDHfLssE8MFtcGCMNzdmC6Rfl9uGydjbhK52vTbcHVD0cKFHdyJcjZs1q

