"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var express_1 = __importDefault(require("express"));
var body_parser_1 = __importDefault(require("body-parser"));
var multer_1 = __importDefault(require("multer"));
var mime_types_1 = __importDefault(require("mime-types"));
var dayjs_1 = __importDefault(require("dayjs"));
var cors_1 = __importDefault(require("cors"));
var checkFileType_1 = require("./utils/checkFileType");
var uniqueId_1 = require("./utils/uniqueId");
var fs_1 = __importDefault(require("fs"));
var tryParseJSONString_1 = require("./utils/tryParseJSONString");
var subfolderName_1 = require("./utils/subfolderName");
// import { hasRequiredFields } from "./utils/hasRequiedFields";
// const __dirname = fileURLToPath(new URL(".", import.meta.url));
// console.log("Starting dev server on ", __dirname);
var getStoragepath = function (subfolderName) {
    return "./uploads/".concat(subfolderName, "/");
};
var storeBase64EncodedFile = function (req, basePath, base64string, fileExtension) {
    // const subfolderName = (req as any as WithCustomData).customData.subfolder;
    // const storagePath = getStoragepath(subfolderName);
    // fs.mkdirSync(storagePath, { recursive: true });
    fs_1.default.mkdirSync(basePath, { recursive: true });
    // console.log("Getting file name ", file.fieldname);
    var uniquePrefix = req.customData.id;
    // console.log("MIME-Type", file.mimetype);
    var mimeType = "image/png";
    // const extension = mime.extension(file.mimetype);
    // console.log("extension", extension);
    // const filename = `${uniquePrefix}-${fieldName}${fileExtension}`;
    var filename = "".concat(uniquePrefix).concat(fileExtension);
    // const path = `${storagePath}${filename}`;
    var path = "".concat(basePath).concat(filename);
    var base64string_clean = base64string.replace(/^data:image\/png;base64,/, "");
    fs_1.default.writeFileSync(path, base64string_clean, "base64");
    return { path: path, basePath: basePath, filename: filename };
};
function createServer() {
    return __awaiter(this, void 0, void 0, function () {
        var app, port, storage, upload;
        var _this = this;
        return __generator(this, function (_a) {
            switch (_a.label) {
                case 0:
                    app = (0, express_1.default)();
                    port = 1337;
                    // HTML templates/views are located in the /views/ directory.
                    app.set("view engine", "ejs");
                    // app.use(bodyParser());
                    app.use(body_parser_1.default.urlencoded());
                    app.use(body_parser_1.default.json({ limit: "2mb" }));
                    // app.use(bodyParser.text({ limit: "200mb" }));
                    // Disabled CORS (attention! this is very unsafe!)
                    app.use((0, cors_1.default)({
                        "allowedHeaders": ["Content-Type"],
                        "origin": "*", // "https://127.0.0.1:8080",
                        "preflightContinue": true
                    }));
                    storage = multer_1.default.diskStorage({
                        destination: function (req, file, cb) {
                            var subfolderName = req.customData.subfolder;
                            // cb(null, "./uploads/");
                            var storagePath = getStoragepath(subfolderName);
                            console.log("destination: ", storagePath);
                            fs_1.default.mkdirSync(storagePath, { recursive: true });
                            cb(null, storagePath);
                        },
                        filename: function (req, file, cb) {
                            // const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
                            console.log("Getting file name ", file.fieldname);
                            var uniquePrefix = req.customData.id;
                            console.log("MIME-Type", file.mimetype);
                            var extension = mime_types_1.default.extension(file.mimetype);
                            console.log("extension", extension);
                            cb(null, "".concat(uniquePrefix, "-").concat(file.fieldname, ".").concat(extension));
                        }
                    });
                    upload = (0, multer_1.default)({
                        storage: storage,
                        limits: { fileSize: 1000000 }, // 1MB file size limit
                        fileFilter: function (req, file, cb) {
                            console.log("File filter called.");
                            // const fieldStatus = hasRequiredFields(req);
                            // if (!fieldStatus.isValid) {
                            //   cb(new Error(fieldStatus.error));
                            //   return;
                            // }
                            // checkFileType(file, cb);
                            var fileStatus = (0, checkFileType_1.checkFileType)(file);
                            if (!fileStatus.isValid) {
                                cb(new Error(fileStatus.error));
                                return;
                            }
                            // Success
                            cb(null, true);
                        }
                    });
                    app.get("/index.html", function (req, res) { return __awaiter(_this, void 0, void 0, function () {
                        var jsonResponse;
                        return __generator(this, function (_a) {
                            // Since `appType` is `'custom'`, should serve response here.
                            // Note: if `appType` is `'spa'` or `'mpa'`, Vite includes middlewares
                            // to handle HTML requests and 404s so user middlewares should be added
                            // before Vite's middlewares to take effect instead
                            console.log("GET");
                            jsonResponse = { message: "OK" };
                            console.log(jsonResponse);
                            res.render("form");
                            return [2 /*return*/];
                        });
                    }); });
                    app.post("/model/put", 
                    // First step: create a unique ID for this request
                    function (req, res, next) {
                        if (!req.customData) {
                            req.customData = { id: (0, uniqueId_1.uniqueId)(), subfolder: (0, subfolderName_1.subfolderName)() };
                        }
                        // console.log("Created an ID for the request", req as any as WithCustomData);
                        next();
                    }, 
                    // Note: _all_ sent fields (!) must be declared here. Otherwise an 'unexpected field' error is thrown.
                    upload.fields([
                        { name: "hidenfield" },
                        { name: "modelName" },
                        { name: "outlineSegmentCount" },
                        { name: "shapeSegmentCount" },
                        { name: "preview2d", maxCount: 1 }, // Not used, using b64 instead
                        { name: "preview3d", maxCount: 1 }, // Not used, using b64 instead
                        { name: "sculptmap", maxCount: 1 }, // Not used, using b64 instead
                        { name: "preview2d_b64", maxCount: 1 },
                        { name: "preview3d_b64", maxCount: 1 },
                        { name: "sculptmap_b64", maxCount: 1 },
                        { name: "bezierJSON" },
                        { name: "bendAngle" }
                    ]), function (req, res) {
                        console.log("POST");
                        // console.log(req.body);
                        // Write JSON files and meta data
                        var uniquePrefix = req.customData.id;
                        var subfolderName = req.customData.subfolder;
                        var storagePath = getStoragepath(subfolderName);
                        // fs.mkdirSync(storagePath, { recursive: true });
                        var modelName = req.body["modelName"];
                        var outlineSegmentCount = req.body["outlineSegmentCount"];
                        var shapeSegmentCount = req.body["shapeSegmentCount"];
                        var bezierJsonRaw = req.body["bezierJSON"];
                        var bendAngleRaw = req.body["bendAngle"];
                        var bendAngle = Number(bendAngleRaw);
                        var bezierData = (0, tryParseJSONString_1.tryParseJSONString)(bezierJsonRaw, null);
                        var preview2d_b64 = req.body["preview2d_b64"];
                        var preview3d_b64 = req.body["preview3d_b64"];
                        var sculptmap_b64 = req.body["sculptmap_b64"];
                        if (!modelName) {
                            return res.status(400).send({ success: false, message: "Param 'modelName' is missing." });
                        }
                        if (!outlineSegmentCount) {
                            return res.status(400).send({ success: false, message: "Param 'outlineSegmentCount' is missing." });
                        }
                        if (!shapeSegmentCount) {
                            return res.status(400).send({ success: false, message: "Param 'shapeSegmentCount' is missing." });
                        }
                        if (!bezierJsonRaw) {
                            return res.status(400).send({ success: false, message: "Param 'bezierJsonRaw' is missing." });
                        }
                        if (!bendAngleRaw) {
                            return res.status(400).send({ success: false, message: "Param 'bendAngleRaw' is missing." });
                        }
                        if (!bendAngle) {
                            return res.status(400).send({ success: false, message: "Param 'bendAngle' is missing." });
                        }
                        if (!bezierData) {
                            return res.status(400).send({ success: false, message: "Param 'bezierData' is missing." });
                        }
                        if (!preview2d_b64) {
                            return res.status(400).send({ success: false, message: "Param 'preview2d_b64' is missing." });
                        }
                        if (!preview3d_b64) {
                            return res.status(400).send({ success: false, message: "Param 'preview3d_b64' is missing." });
                        }
                        if (!sculptmap_b64) {
                            return res.status(400).send({ success: false, message: "Param 'sculptmap_b64' is missing." });
                        }
                        var filepath_preview2d = storeBase64EncodedFile(req, storagePath + "preview2d/", preview2d_b64, ".png");
                        var filepath_preview3d = storeBase64EncodedFile(req, storagePath + "preview3d/", preview3d_b64, ".png");
                        var filepath_sculptmap = storeBase64EncodedFile(req, storagePath + "sculptmap/", sculptmap_b64, ".png");
                        fs_1.default.writeFileSync("./".concat(storagePath).concat(uniquePrefix, "-meta.json"), JSON.stringify({
                            date: (0, dayjs_1.default)().format(), // ISO data
                            remoteIp: req.ip,
                            version: "0.0.2",
                            name: modelName,
                            outlineSegmentCount: outlineSegmentCount,
                            shapeSegmentCount: shapeSegmentCount,
                            filepath_preview2d: filepath_preview2d.filename,
                            filepath_preview3d: filepath_preview3d.filename,
                            filepath_sculptmap: filepath_sculptmap.filename,
                            bezierData: bezierData,
                            bezierDataRaw: bezierJsonRaw,
                            bendAngle: bendAngle,
                            bendAngleRaw: bendAngleRaw
                        }, null, 2));
                        var jsonResponse = { message: "OK" };
                        console.log(jsonResponse);
                        res.json(jsonResponse);
                    });
                    return [4 /*yield*/, app.listen(port, function () {
                            console.log("Example app listening on port ".concat(port));
                        })];
                case 1:
                    _a.sent();
                    return [2 /*return*/];
            }
        });
    });
}
createServer();
