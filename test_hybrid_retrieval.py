
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.retrieval_service import retrieval_service


def test_hybrid_retrieval():
    # Open a database session.
    db = SessionLocal()

    try:
        # Find an existing document that has completed processing.
        document = (
            db.query(Document)
            .filter(Document.status == "ready")
            .first()
        )

        if document is None:
            raise RuntimeError("No ready document found in PostgreSQL.")

        # Find the first chunk belonging to this document.
        source_chunk = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index.asc())
            .first()
        )

        if source_chunk is None:
            raise RuntimeError("The selected document has no chunks.")

        # Use actual document text to create a relevant test question.
        question = source_chunk.content[:300].strip()

        if not question:
            raise RuntimeError("The selected chunk contains no text.")

        print("\n========== HYBRID RETRIEVAL TEST ==========")
        print("Document:", document.filename)
        print("Document ID:", document.id)
        print("User ID:", document.user_id)
        print("Test question:", question)

        # Execute the existing dense + sparse hybrid retrieval pipeline.
        results = retrieval_service.retrieve(
            db=db,
            question=question,
            user_id=document.user_id,
            document_id=document.id,
            limit=5,
        )

        # Ensure retrieval returned at least one result.
        if not results:
            raise AssertionError("Hybrid retrieval returned no results.")

        print("\nRetrieved chunks:", len(results))

        # Track whether the original source chunk appears in the results.
        matching_chunk = False

        # Inspect and validate every retrieved chunk.
        for index, result in enumerate(results, start=1):
            print(f"\n--- Result {index} ---")
            print("Chunk ID:", result.chunk_id)
            print("Document:", result.filename)
            print("Chunk index:", result.chunk_index)
            print("Score:", result.score)
            print("Content:", result.text[:250])

            # Display document IDs and their Python types for diagnosis.
            print(
                "Expected document ID:",
                document.id,
                type(document.id),
            )
            print(
                "Retrieved document ID:",
                result.document_id,
                type(result.document_id),
            )

            # Normalize both UUID values to strings for comparison.
            expected_id = str(document.id)
            retrieved_id = str(result.document_id)

            # Every result must belong to the requested document.
            assert retrieved_id == expected_id, (
                f"Document ID mismatch: expected {expected_id}, "
                f"received {retrieved_id}"
            )

            # Verify that PostgreSQL chunk content was returned.
            assert result.text is not None
            assert result.text.strip()

            # Check whether the original source chunk was retrieved.
            if str(result.chunk_id) == str(source_chunk.id):
                matching_chunk = True

        if matching_chunk:
            print("\nPASS: Original source chunk was retrieved.")
        else:
            print(
                "\nWARNING: Original source chunk was not in the top results."
            )

        print("\nHYBRID RETRIEVAL EXECUTION PASSED.")

    finally:
        # Always close the database session.
        db.close()


if __name__ == "__main__":
    test_hybrid_retrieval()
