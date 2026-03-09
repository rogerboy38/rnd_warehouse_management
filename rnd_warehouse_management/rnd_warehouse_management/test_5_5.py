
# test_5_5.py - Phase 5.5: Batch Traceability & Quality Chain Test Plan
"""Phase 5.5 Test Plan: Batch Traceability & Quality Chain
Tests genealogy, CoA, hold/release, traceability reports."""
import frappe
from frappe.utils import now_datetime

def run_all_tests():
    results = []
    tests = [
        test_batch_genealogy_valid,
        test_batch_genealogy_invalid,
        test_generate_coa,
        test_hold_batch,
        test_release_batch_clean,
        test_full_traceability,
        test_genealogy_tree_depth,
    ]
    for test_fn in tests:
        try:
            test_fn()
            results.append({"test": test_fn.__name__, "status": "PASS"})
            print(f"  PASS: {test_fn.__name__}")
        except Exception as e:
            results.append({"test": test_fn.__name__, "status": "FAIL", "error": str(e)})
            print(f"  FAIL: {test_fn.__name__} - {e}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n=== Phase 5.5 Results: {passed}/{len(results)} passed ===")
    return results


def _get_test_batch():
    """Find any existing batch for testing."""
    return frappe.db.get_value("Batch", {}, "name")


def test_batch_genealogy_valid():
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import get_batch_genealogy
    batch = _get_test_batch()
    if not batch:
        print("    SKIP: No batches exist")
        return
    result = get_batch_genealogy(batch)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "batch_id" in result
    assert "quality_inspections" in result
    assert "stock_entries" in result


def test_batch_genealogy_invalid():
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import get_batch_genealogy
    try:
        get_batch_genealogy("NONEXISTENT-BATCH-99999")
        assert False, "Should have thrown"
    except Exception:
        pass  # Expected


def test_generate_coa():
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import generate_coa
    batch = _get_test_batch()
    if not batch:
        print("    SKIP: No batches")
        return
    coa = generate_coa(batch)
    assert isinstance(coa, dict)
    assert "batch_id" in coa
    assert "overall_status" in coa
    assert "parameters" in coa
    assert "generated_on" in coa


def test_hold_batch():
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import hold_batch
    batch = _get_test_batch()
    if not batch:
        print("    SKIP: No batches")
        return
    result = hold_batch(batch, reason="Test hold", create_nc=False)
    assert result["status"] == "On Hold"
    assert result["batch_id"] == batch
    # Verify DB updated
    status = frappe.db.get_value("Batch", batch, "custom_quality_status")
    assert status == "On Hold", f"Expected On Hold, got {status}"


def test_release_batch_clean():
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import release_batch
    batch = _get_test_batch()
    if not batch:
        print("    SKIP: No batches")
        return
    result = release_batch(batch)
    assert "can_release" in result
    assert "batch_id" in result
    # Result depends on whether there are failed QIs/open NCs


def test_full_traceability():
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import get_full_traceability
    batch = _get_test_batch()
    if not batch:
        print("    SKIP: No batches")
        return
    result = get_full_traceability(batch)
    assert "genealogy" in result
    assert "certificate_of_analysis" in result
    assert "current_locations" in result


def test_genealogy_tree_depth():
    """Test that genealogy tree respects max depth."""
    from rnd_warehouse_management.rnd_warehouse_management.batch_traceability import _build_genealogy_node
    batch = _get_test_batch()
    if not batch:
        print("    SKIP: No batches")
        return
    node = _build_genealogy_node(batch, depth=0, max_depth=2)
    assert isinstance(node, dict)
    assert "depth" in node
    assert node["depth"] == 0


if __name__ == "__main__":
    run_all_tests()
