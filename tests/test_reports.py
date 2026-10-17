from openpyxl import load_workbook

from storepro.reports import Reports
from storepro.catalog import Catalog
from storepro.sales import Sales
from storepro.exports import export_rows, render_receipt


def test_report_historical_cost_and_returns(env, tmp_path):
    db, user = env
    catalog = Catalog(db)

    product = catalog.save_product(
        user,
        dict(name="سكر", cost=200, price=500),
    )
    catalog.adjust(user, product, 2000, "initial")

    sales = Sales(db)
    invoice = sales.checkout(
        user,
        [dict(product_id=product, qty=2000)],
        0,
        1400,
        dict(cash=1140),
        None,
        "a",
    )

    with db.transaction() as connection:
        connection.execute(
            "UPDATE products SET cost=900 WHERE id=?",
            (product,),
        )

    item = sales.detail(invoice)["items"][0]["id"]
    sales.refund(
        user,
        invoice,
        [dict(item_id=item, qty=1000)],
        "cash",
    )

    report = Reports(db).summary("2000-01-01", "2099-01-01")

    assert report["net_sales"] == 500
    assert report["tax"] == 70
    assert report["profit"] == 300
    assert report["refunds"] == 570
    assert report["sales"] == 1140

    assert Reports(db).summary(
        "2000-01-01", "2000-01-02"
    )["sales"] == 0

    assert Reports(db).table(
        "products", "2000-01-01", "2099-01-01"
    )[0]["name"] == "سكر"

    rows = [{"اسم": "سكر", "قيمة": "=1+1"}]

    for extension in ("csv", "xlsx", "pdf"):
        path = tmp_path / f"report.{extension}"
        export_rows(rows, path)

        assert path.stat().st_size > 0

        if extension == "csv":
            assert "سكر" in path.read_text(encoding="utf-8-sig")

    book = load_workbook(tmp_path / "report.xlsx")
    try:
        assert book.active["B2"].data_type == "s"
    finally:
        book.close()

    receipt = render_receipt(
        sales.detail(invoice),
        tmp_path / "receipt.html",
        58,
    )
    text = receipt.read_text(encoding="utf-8")

    assert "سكر" in text
    assert "SP-" in text
    assert "58mm" in text