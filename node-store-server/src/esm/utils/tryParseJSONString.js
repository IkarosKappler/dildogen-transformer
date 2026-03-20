"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.tryParseJSONString = void 0;
var tryParseJSONString = function (jsonString, fallback) {
    try {
        return JSON.parse(jsonString);
    }
    catch (e) {
        return fallback;
    }
};
exports.tryParseJSONString = tryParseJSONString;
