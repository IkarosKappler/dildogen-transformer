"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.hasRequiredFields = void 0;
var hasRequiredFields = function (req) {
    // 1. Implement this!
    // const modelName = req.body["model-name"];
    //   const bezierJsonRaw = req.body["bezier-json"];
    //   const bendAngleRaw = req.body["bend-angle"];
    if (!req.body["model-name"]) {
        return { isValid: false, error: "Param 'mode-name' is missing." };
    }
    if (!req.body["bezier-json"]) {
        return { isValid: false, error: "Param 'bezier-json' is missing." };
    }
    if (!req.body["bend-angle"]) {
        return { isValid: false, error: "Param 'bend-angle' is missing." };
    }
    return { isValid: true, error: null };
};
exports.hasRequiredFields = hasRequiredFields;
