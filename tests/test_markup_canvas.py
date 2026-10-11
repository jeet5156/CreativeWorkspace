"""Unit tests for MarkupCanvas UI widget: pins, arrows, freehand strokes, selection, move, delete, undo/redo, coordinate conversions."""

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from models.markup import MarkupDocument
from services.markup_service import MarkupService
from ui.widgets.markup_canvas import MarkupCanvas, MarkupCanvasView, MarkupTool

app = QApplication.instance() or QApplication([])


class TestMarkupCanvas(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cw_test_canvas_")
        self.storage_dir = Path(self.test_dir) / "markups"
        self.markup_service = MarkupService(storage_dir=self.storage_dir)

        self.canvas = MarkupCanvas()
        self.canvas.resize(800, 600)
        self.canvas.set_markup_service(self.markup_service)
        self.canvas.show()

        # Create a test image: 1000x500 pixels
        self.image_width = 1000
        self.image_height = 500
        self.test_image = QImage(self.image_width, self.image_height, QImage.Format_RGB32)
        self.test_image.fill(QColor("#222222"))

        # Load image into canvas
        success = self.canvas.set_image(self.test_image)
        self.assertTrue(success)

    def tearDown(self):
        self.canvas.close()
        self.canvas.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_image_loading_and_properties(self):
        """Verify image loading sets dimensions and state correctly."""
        self.assertTrue(self.canvas.has_image())
        sz = self.canvas.view.image_size
        self.assertEqual(sz.width(), 1000)
        self.assertEqual(sz.height(), 500)

    def test_coordinate_conversion_key_points(self):
        """Verify top-left, center, and bottom-right coordinate mapping."""
        top_left_img = QPointF(0.0, 0.0)
        center_img = QPointF(500.0, 250.0)
        bottom_right_img = QPointF(1000.0, 500.0)

        norm_tl = self.canvas.image_to_normalized(top_left_img)
        self.assertAlmostEqual(norm_tl.x(), 0.0, places=4)
        self.assertAlmostEqual(norm_tl.y(), 0.0, places=4)

        norm_ctr = self.canvas.image_to_normalized(center_img)
        self.assertAlmostEqual(norm_ctr.x(), 0.5, places=4)
        self.assertAlmostEqual(norm_ctr.y(), 0.5, places=4)

        norm_br = self.canvas.image_to_normalized(bottom_right_img)
        self.assertAlmostEqual(norm_br.x(), 1.0, places=4)
        self.assertAlmostEqual(norm_br.y(), 1.0, places=4)

        img_tl = self.canvas.normalized_to_image(norm_tl)
        self.assertAlmostEqual(img_tl.x(), 0.0, places=4)
        self.assertAlmostEqual(img_tl.y(), 0.0, places=4)

        img_ctr = self.canvas.normalized_to_image(norm_ctr)
        self.assertAlmostEqual(img_ctr.x(), 500.0, places=4)
        self.assertAlmostEqual(img_ctr.y(), 250.0, places=4)

    def test_round_trip_view_to_normalized(self):
        """Verify normalized -> view -> normalized round-trip stability."""
        test_norm_points = [
            (0.1, 0.2),
            (0.5, 0.5),
            (0.85, 0.95),
            (0.0, 0.0),
            (1.0, 1.0),
        ]

        for u, v in test_norm_points:
            view_pt = self.canvas.normalized_to_view((u, v))
            self.assertIsNotNone(view_pt)

            re_norm = self.canvas.view_to_normalized(view_pt)
            self.assertIsNotNone(re_norm)
            self.assertAlmostEqual(re_norm.x(), u, places=3)
            self.assertAlmostEqual(re_norm.y(), v, places=3)

    def test_zoom_stability(self):
        """Verify normalized coordinate conversions remain stable across arbitrary zoom levels."""
        u, v = 0.35, 0.65

        zoom_levels = [0.25, 0.5, 1.0, 2.0, 4.0]
        for z in zoom_levels:
            self.canvas.set_zoom_level(z)
            self.assertAlmostEqual(self.canvas.get_zoom_level(), z, places=3)

            view_pt = self.canvas.normalized_to_view((u, v))
            re_norm = self.canvas.view_to_normalized(view_pt)
            self.assertAlmostEqual(re_norm.x(), u, places=3)
            self.assertAlmostEqual(re_norm.y(), v, places=3)

    def test_pan_stability(self):
        """Verify panning viewport does not alter normalized coordinate mapping."""
        u, v = 0.4, 0.7
        self.canvas.set_zoom_level(2.0)

        h_bar = self.canvas.view.horizontalScrollBar()
        v_bar = self.canvas.view.verticalScrollBar()
        if h_bar.maximum() > 0:
            h_bar.setValue(h_bar.maximum() // 2)
        if v_bar.maximum() > 0:
            v_bar.setValue(v_bar.maximum() // 2)

        view_pt = self.canvas.normalized_to_view((u, v))
        re_norm = self.canvas.view_to_normalized(view_pt)
        self.assertAlmostEqual(re_norm.x(), u, places=3)
        self.assertAlmostEqual(re_norm.y(), v, places=3)

    def test_resize_stability(self):
        """Verify resizing canvas maintains accurate normalized coordinates."""
        u, v = 0.6, 0.25

        self.canvas.resize(1200, 900)
        app.processEvents()

        view_pt = self.canvas.normalized_to_view((u, v))
        re_norm = self.canvas.view_to_normalized(view_pt)
        self.assertAlmostEqual(re_norm.x(), u, places=3)
        self.assertAlmostEqual(re_norm.y(), v, places=3)

        self.canvas.resize(400, 300)
        app.processEvents()

        view_pt2 = self.canvas.normalized_to_view((u, v))
        re_norm2 = self.canvas.view_to_normalized(view_pt2)
        self.assertAlmostEqual(re_norm2.x(), u, places=3)
        self.assertAlmostEqual(re_norm2.y(), v, places=3)

    def test_fit_and_actual_zoom_modes(self):
        """Verify Fit and 100% zoom controls."""
        self.canvas.zoom_to_actual()
        self.assertAlmostEqual(self.canvas.get_zoom_level(), 1.0, places=3)

        self.canvas.zoom_to_fit()
        fit_zoom = self.canvas.get_zoom_level()
        self.assertGreater(fit_zoom, 0.0)

    def test_tool_switching(self):
        """Verify switching between SELECT, PIN, ARROW, and FREEHAND/DRAW tool modes."""
        self.assertEqual(self.canvas.current_tool(), MarkupTool.SELECT)

        # Switch to PIN
        self.canvas.set_tool(MarkupTool.PIN)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.PIN)
        self.assertEqual(self.canvas.toolbar._active_tool, MarkupTool.PIN)

        # Switch to ARROW
        self.canvas.set_tool(MarkupTool.ARROW)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.ARROW)
        self.assertEqual(self.canvas.toolbar._active_tool, MarkupTool.ARROW)

        # Switch to FREEHAND / DRAW
        self.canvas.set_tool(MarkupTool.FREEHAND)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.FREEHAND)
        self.assertEqual(self.canvas.toolbar._active_tool, MarkupTool.FREEHAND)

        # Switch back to SELECT
        self.canvas.set_tool(MarkupTool.SELECT)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.SELECT)
        self.assertEqual(self.canvas.toolbar._active_tool, MarkupTool.SELECT)

    def test_interactive_pin_creation_and_persistence(self):
        """Verify creating a pin annotation, persistence via MarkupService, and automatic selection."""
        source_ref = {"source_type": "project_asset", "project_id": "proj_1", "relative_path": "Renders/hero.png"}
        doc = self.markup_service.create_markup(source_ref, name="Hero Review")
        self.canvas.set_document(doc)

        norm_pos = QPointF(0.42, 0.63)
        ann_id = self.canvas.create_pin_annotation(norm_pos, "Fix topology around eye")
        self.assertIsNotNone(ann_id)
        self.assertTrue(ann_id.startswith("ann_"))

        self.assertEqual(len(self.canvas.view._annotation_items), 1)
        self.assertIn(ann_id, self.canvas.view._annotation_items)
        self.assertEqual(self.canvas.selected_annotation_id(), ann_id)

        persisted_doc = self.markup_service.get_markup(doc.id)
        self.assertIsNotNone(persisted_doc)
        self.assertEqual(len(persisted_doc.annotations), 1)
        ann_record = persisted_doc.annotations[0]
        self.assertEqual(ann_record["id"], ann_id)
        self.assertEqual(ann_record["type"], "text")
        self.assertEqual(ann_record["text"], "Fix topology around eye")
        self.assertAlmostEqual(ann_record["position"]["x"], 0.42, places=3)
        self.assertAlmostEqual(ann_record["position"]["y"], 0.63, places=3)

    def test_arrow_creation_and_persistence(self):
        """Verify creating a vector arrow annotation with normalized endpoints and persistence."""
        doc = self.markup_service.create_markup({"source_type": "project_asset"})
        self.canvas.set_document(doc)

        start_norm = QPointF(0.25, 0.30)
        end_norm = QPointF(0.60, 0.70)
        ann_id = self.canvas.create_arrow_annotation(start_norm, end_norm)

        self.assertIsNotNone(ann_id)
        self.assertEqual(len(self.canvas.view._annotation_items), 1)
        self.assertIn(ann_id, self.canvas.view._annotation_items)
        self.assertEqual(self.canvas.selected_annotation_id(), ann_id)

        persisted = self.markup_service.get_markup(doc.id)
        self.assertEqual(len(persisted.annotations), 1)
        record = persisted.annotations[0]
        self.assertEqual(record["id"], ann_id)
        self.assertEqual(record["type"], "arrow")
        self.assertAlmostEqual(record["start"]["x"], 0.25, places=3)
        self.assertAlmostEqual(record["start"]["y"], 0.30, places=3)
        self.assertAlmostEqual(record["end"]["x"], 0.60, places=3)
        self.assertAlmostEqual(record["end"]["y"], 0.70, places=3)

    def test_arrow_drag_interaction_and_cancellation(self):
        """Verify mouse drag creates arrow and Escape cancels in-progress preview."""
        doc = self.markup_service.create_markup({"source_type": "project_asset"})
        self.canvas.set_document(doc)
        self.canvas.zoom_to_actual()

        self.canvas.set_tool(MarkupTool.ARROW)

        p1 = self.canvas.normalized_to_view((0.1, 0.2)).toPoint()
        p2 = self.canvas.normalized_to_view((0.5, 0.6)).toPoint()

        event_press = QMouseEvent(QEvent.MouseButtonPress, QPointF(p1), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.canvas.view.mousePressEvent(event_press)
        self.assertTrue(self.canvas.view._is_drawing_arrow)
        self.assertIsNotNone(self.canvas.view._temp_arrow_item)

        event_move = QMouseEvent(QEvent.MouseMove, QPointF(p2), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        self.canvas.view.mouseMoveEvent(event_move)

        event_release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(p2), Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        self.canvas.view.mouseReleaseEvent(event_release)

        self.assertEqual(len(self.canvas.view._annotation_items), 1)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.SELECT)

        # Test Escape preview cancellation
        self.canvas.set_tool(MarkupTool.ARROW)
        self.canvas.view.mousePressEvent(event_press)
        self.assertTrue(self.canvas.view._is_drawing_arrow)

        event_esc = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        self.canvas.view.keyPressEvent(event_esc)
        self.assertFalse(self.canvas.view._is_drawing_arrow)
        self.assertIsNone(self.canvas.view._temp_arrow_item)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.SELECT)

    def test_freehand_creation_and_persistence(self):
        """Verify creating a freehand stroke annotation with normalized point list."""
        doc = self.markup_service.create_markup({"source_type": "project_asset"})
        self.canvas.set_document(doc)

        pts = [
            {"x": 0.20, "y": 0.30},
            {"x": 0.25, "y": 0.35},
            {"x": 0.30, "y": 0.40},
            {"x": 0.35, "y": 0.45},
        ]
        ann_id = self.canvas.create_freehand_annotation(pts)

        self.assertIsNotNone(ann_id)
        self.assertEqual(len(self.canvas.view._annotation_items), 1)
        self.assertIn(ann_id, self.canvas.view._annotation_items)
        self.assertEqual(self.canvas.selected_annotation_id(), ann_id)

        persisted = self.markup_service.get_markup(doc.id)
        self.assertEqual(len(persisted.annotations), 1)
        record = persisted.annotations[0]
        self.assertEqual(record["id"], ann_id)
        self.assertEqual(record["type"], "freehand")
        self.assertEqual(len(record["points"]), 4)
        self.assertAlmostEqual(record["points"][0]["x"], 0.20, places=3)
        self.assertAlmostEqual(record["points"][-1]["y"], 0.45, places=3)

    def test_freehand_drag_interaction_and_cancellation(self):
        """Verify interactive freehand stroke drawing and Escape key cancellation."""
        doc = self.markup_service.create_markup({"source_type": "project_asset"})
        self.canvas.set_document(doc)
        self.canvas.zoom_to_actual()

        self.canvas.set_tool(MarkupTool.FREEHAND)

        p1 = self.canvas.normalized_to_view((0.1, 0.1)).toPoint()
        p2 = self.canvas.normalized_to_view((0.15, 0.2)).toPoint()
        p3 = self.canvas.normalized_to_view((0.2, 0.3)).toPoint()

        # Press
        event_press = QMouseEvent(QEvent.MouseButtonPress, QPointF(p1), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.canvas.view.mousePressEvent(event_press)
        self.assertTrue(self.canvas.view._is_drawing_freehand)
        self.assertIsNotNone(self.canvas.view._temp_stroke_item)

        # Moves
        event_m1 = QMouseEvent(QEvent.MouseMove, QPointF(p2), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        self.canvas.view.mouseMoveEvent(event_m1)
        event_m2 = QMouseEvent(QEvent.MouseMove, QPointF(p3), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        self.canvas.view.mouseMoveEvent(event_m2)

        # Release
        event_release = QMouseEvent(QEvent.MouseButtonRelease, QPointF(p3), Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        self.canvas.view.mouseReleaseEvent(event_release)

        self.assertEqual(len(self.canvas.view._annotation_items), 1)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.SELECT)

        # Escape cancellation
        self.canvas.set_tool(MarkupTool.FREEHAND)
        self.canvas.view.mousePressEvent(event_press)
        self.assertTrue(self.canvas.view._is_drawing_freehand)

        event_esc = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        self.canvas.view.keyPressEvent(event_esc)
        self.assertFalse(self.canvas.view._is_drawing_freehand)
        self.assertIsNone(self.canvas.view._temp_stroke_item)
        self.assertEqual(self.canvas.current_tool(), MarkupTool.SELECT)

    def test_freehand_movement_and_undo_redo(self):
        """Verify translating a freehand stroke offsets all points and integrates with Undo/Redo."""
        doc = self.markup_service.create_markup({"source_type": "project_asset"})
        self.canvas.set_document(doc)

        pts = [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}, {"x": 0.3, "y": 0.3}]
        ann_id = self.canvas.create_freehand_annotation(pts)

        from ui.widgets.markup_canvas import MoveAnnotationCommand
        old_geom = {"points": copy.deepcopy(pts)}
        new_geom = {"points": [{"x": 0.3, "y": 0.3}, {"x": 0.4, "y": 0.4}, {"x": 0.5, "y": 0.5}]}
        cmd = MoveAnnotationCommand(self.canvas.view, doc.id, ann_id, old_geom, new_geom)
        cmd.execute()
        self.canvas.view.undo_stack.push(cmd)
        self.canvas.view.undo_stack_changed.emit()

        persisted = self.markup_service.get_markup(doc.id)
        self.assertAlmostEqual(persisted.annotations[0]["points"][0]["x"], 0.3, places=3)
        self.assertAlmostEqual(persisted.annotations[0]["points"][-1]["y"], 0.5, places=3)

        # Undo move
        self.canvas.undo()
        persisted_undo = self.markup_service.get_markup(doc.id)
        self.assertAlmostEqual(persisted_undo.annotations[0]["points"][0]["x"], 0.1, places=3)
        self.assertAlmostEqual(persisted_undo.annotations[0]["points"][-1]["y"], 0.3, places=3)

        # Redo move
        self.canvas.redo()
        persisted_redo = self.markup_service.get_markup(doc.id)
        self.assertAlmostEqual(persisted_redo.annotations[0]["points"][0]["x"], 0.3, places=3)
        self.assertAlmostEqual(persisted_redo.annotations[0]["points"][-1]["y"], 0.5, places=3)

    def test_freehand_deletion_and_undo_redo(self):
        """Verify deleting a freehand stroke and restoring exact point list via Undo."""
        doc = self.markup_service.create_markup({"source_type": "project_asset"})
        self.canvas.set_document(doc)

        pts = [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}, {"x": 0.5, "y": 0.6}]
        ann_id = self.canvas.create_freehand_annotation(pts)
        self.assertEqual(len(self.canvas.view._annotation_items), 1)

        # Delete
        self.canvas.select_annotation(ann_id)
        event_del = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        self.canvas.view.keyPressEvent(event_del)

        self.assertEqual(len(self.canvas.view._annotation_items), 0)
        persisted_empty = self.markup_service.get_markup(doc.id)
        self.assertEqual(len(persisted_empty.annotations), 0)

        # Undo -> Restores complete stroke
        self.canvas.undo()
        self.assertEqual(len(self.canvas.view._annotation_items), 1)
        persisted_restored = self.markup_service.get_markup(doc.id)
        self.assertEqual(len(persisted_restored.annotations), 1)
        self.assertEqual(persisted_restored.annotations[0]["id"], ann_id)
        self.assertEqual(persisted_restored.annotations[0]["type"], "freehand")
        self.assertEqual(len(persisted_restored.annotations[0]["points"]), 3)

        # Redo -> Deletes again
        self.canvas.redo()
        self.assertEqual(len(self.canvas.view._annotation_items), 0)


if __name__ == "__main__":
    import copy
    unittest.main()
