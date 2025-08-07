from unittest import TestCase

from test.test_builders import create_map_descriptor


class TestMappingToolDescriptor(TestCase):

    def test_to_mapping_tool_string(self):
        descriptor_default = create_map_descriptor()
        descriptor_with_suffix = create_map_descriptor(quantity_suffix="NotDefault")

        cases = [
            (descriptor_default, "h90-enaCUSTOM-h-sf-sp-ram-hae-2deg-6mo"),
            (descriptor_with_suffix, "h90-enaNotDefault-h-sf-sp-ram-hae-2deg-6mo")
        ]

        for descriptor, expected_string in cases:
            with self.subTest(descriptor):
                actual_string = descriptor.to_mapping_tool_string()
                self.assertEqual(expected_string, actual_string)

    def test_mapping_tool_descriptor_to_string(self):
        mapping_tool_descriptor = create_map_descriptor(quantity_suffix="suffix")

        expected_map_descriptor_string = "h90-ena-h-sf-sp-ram-hae-2deg-6mo"
        actual_map_descriptor_string = mapping_tool_descriptor.to_string()
        self.assertEqual(expected_map_descriptor_string, actual_map_descriptor_string)
