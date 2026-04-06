"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.tryParseJSONString = void 0;
const tryParseJSONString = (jsonString, fallback) => {
    try {
        return JSON.parse(jsonString);
    }
    catch (e) {
        return fallback;
    }
};
exports.tryParseJSONString = tryParseJSONString;
