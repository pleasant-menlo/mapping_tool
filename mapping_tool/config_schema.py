schema = {
    "type": "object",
    "properties": {
        "canonical_map_period": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer"
                },
                "quarter": {
                    "type": "integer"
                },
                "map_period": {
                    "type": "integer"
                },
                "number_of_maps": {
                    "type": "integer"
                }
            },
            "required": [
                "year",
                "quarter",
                "map_period",
                "number_of_maps"
            ]
        },
        "instruments": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": [
                    "Hi 45",
                    "Hi 90",
                    "Hi combined",
                    "Ultra 45",
                    "Ultra 90",
                    "Ultra combined",
                    "Lo",
                    "lo",
                    "GLOWS",
                    "glows",
                    "IDEX",
                    "idex"
                ]
            }
        },
        "spin_phase": {
            "type": "string",
            "enum": [
                "ram",
                "Ram",
                "Anti-ram",
                "anti-ram",
                "Full spin",
                "full spin"
            ]
        },
        "reference_frame": {
            "type": "string",
            "enum": [
                "spacecraft",
                "heliospheric",
                "heliospheric kinematic"
            ]
        },
        "survival_corrected": {
            "type": "boolean"
        },
        "spice_frame_name": {
            "type": "string"
        },
        "pixelation_scheme": {
            "type": "string",
            "enum": [
                "Square",
                "square",
                "HEALPIX",
                "healpix"
            ]
        },
        "pixel_parameter": {
            "type": "integer",
            "enum": [
                2,
                4,
                6,
                16,
                32,
                64,
                128,
                256,
                512
            ]
        },
        "map_data_type": {
            "type": "string",
            "enum": [
                "ENA Intensity",
                "Spectral Index"
            ]
        },
        "lo_species": {
            "type": "string",
            "enum": [
                "H",
                "h",
                "O",
                "o"
            ]
        },
        "output_directory": {
            "type": "string"
        },
        "output_files": {
            "type": "object",
            "properties": {
                "Hi 45": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "Hi 90": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "Hi combined": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "Ultra 45": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "Ultra 90": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "Ultra combined": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "Lo": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "lo": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "GLOWS": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "glows": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "IDEX": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                },
                "idex": {
                    "type": "array",
                    "item": {
                        "type": "string"
                    }
                }
            }
        }
    },
    "required": [
        "canonical_map_period",
        "instruments",
        "spin_phase",
        "reference_frame",
        "survival_corrected",
        "spice_frame_name",
        "pixelation_scheme",
        "pixel_parameter",
        "map_data_type"
    ]
}
