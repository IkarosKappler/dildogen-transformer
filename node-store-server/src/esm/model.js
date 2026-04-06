"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const body_parser_1 = __importDefault(require("body-parser"));
const multer_1 = __importDefault(require("multer"));
const mime_types_1 = __importDefault(require("mime-types"));
const dayjs_1 = __importDefault(require("dayjs"));
const cors_1 = __importDefault(require("cors"));
const checkFileType_1 = require("./utils/checkFileType");
const uniqueId_1 = require("./utils/uniqueId");
const fs_1 = __importDefault(require("fs"));
const tryParseJSONString_1 = require("./utils/tryParseJSONString");
const subfolderName_1 = require("./utils/subfolderName");
// import { hasRequiredFields } from "./utils/hasRequiedFields";
// const __dirname = fileURLToPath(new URL(".", import.meta.url));
// console.log("Starting dev server on ", __dirname);
const getStoragepath = (subfolderName) => {
    return `./uploads/${subfolderName}/`;
};
const storeBase64EncodedFile = (req, basePath, base64string, fileExtension) => {
    // const subfolderName = (req as any as WithCustomData).customData.subfolder;
    // const storagePath = getStoragepath(subfolderName);
    // fs.mkdirSync(storagePath, { recursive: true });
    fs_1.default.mkdirSync(basePath, { recursive: true });
    // console.log("Getting file name ", file.fieldname);
    const uniquePrefix = req.customData.id;
    // console.log("MIME-Type", file.mimetype);
    const mimeType = "image/png";
    // const extension = mime.extension(file.mimetype);
    // console.log("extension", extension);
    // const filename = `${uniquePrefix}-${fieldName}${fileExtension}`;
    const filename = `${uniquePrefix}${fileExtension}`;
    // const path = `${storagePath}${filename}`;
    const path = `${basePath}${filename}`;
    var base64string_clean = base64string.replace(/^data:image\/png;base64,/, "");
    fs_1.default.writeFileSync(path, base64string_clean, "base64");
    return { path: path, basePath: basePath, filename: filename };
};
async function createServer() {
    const app = (0, express_1.default)();
    const port = 1337;
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
    const storage = multer_1.default.diskStorage({
        destination: function (req, file, cb) {
            const subfolderName = req.customData.subfolder;
            // cb(null, "./uploads/");
            const storagePath = getStoragepath(subfolderName);
            console.log("destination: ", storagePath);
            fs_1.default.mkdirSync(storagePath, { recursive: true });
            cb(null, storagePath);
        },
        filename: function (req, file, cb) {
            // const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
            console.log("Getting file name ", file.fieldname);
            const uniquePrefix = req.customData.id;
            console.log("MIME-Type", file.mimetype);
            const extension = mime_types_1.default.extension(file.mimetype);
            console.log("extension", extension);
            cb(null, `${uniquePrefix}-${file.fieldname}.${extension}`);
        }
    });
    const upload = (0, multer_1.default)({
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
            const fileStatus = (0, checkFileType_1.checkFileType)(file);
            if (!fileStatus.isValid) {
                cb(new Error(fileStatus.error));
                return;
            }
            // Success
            cb(null, true);
        }
    });
    app.get("/index.html", async (req, res) => {
        // Since `appType` is `'custom'`, should serve response here.
        // Note: if `appType` is `'spa'` or `'mpa'`, Vite includes middlewares
        // to handle HTML requests and 404s so user middlewares should be added
        // before Vite's middlewares to take effect instead
        console.log("GET");
        const jsonResponse = { message: "OK" };
        console.log(jsonResponse);
        res.render("form");
    });
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
        const uniquePrefix = req.customData.id;
        const subfolderName = req.customData.subfolder;
        const storagePath = getStoragepath(subfolderName);
        // fs.mkdirSync(storagePath, { recursive: true });
        const modelName = req.body["modelName"];
        const outlineSegmentCount = req.body["outlineSegmentCount"];
        const shapeSegmentCount = req.body["shapeSegmentCount"];
        const bezierJsonRaw = req.body["bezierJSON"];
        const bendAngleRaw = req.body["bendAngle"];
        const bendAngle = Number(bendAngleRaw);
        const bezierData = (0, tryParseJSONString_1.tryParseJSONString)(bezierJsonRaw, null);
        const preview2d_b64 = req.body["preview2d_b64"];
        const preview3d_b64 = req.body["preview3d_b64"];
        const sculptmap_b64 = req.body["sculptmap_b64"];
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
        const filepath_preview2d = storeBase64EncodedFile(req, storagePath + "preview2d/", preview2d_b64, ".png");
        const filepath_preview3d = storeBase64EncodedFile(req, storagePath + "preview3d/", preview3d_b64, ".png");
        const filepath_sculptmap = storeBase64EncodedFile(req, storagePath + "sculptmap/", sculptmap_b64, ".png");
        fs_1.default.writeFileSync(`./${storagePath}${uniquePrefix}-meta.json`, JSON.stringify({
            date: (0, dayjs_1.default)().format(), // ISO data
            remoteIp: req.ip,
            version: "0.0.3",
            name: modelName,
            outlineSegmentCount: outlineSegmentCount,
            shapeSegmentCount: shapeSegmentCount,
            filepath_preview2d: "./preview2d/" + filepath_preview2d.filename,
            filepath_preview3d: "./preview3d/" + filepath_preview3d.filename,
            filepath_sculptmap: "./sculptmap/" + filepath_sculptmap.filename,
            bezierData: bezierData,
            bezierDataRaw: bezierJsonRaw,
            bendAngle: bendAngle,
            bendAngleRaw: bendAngleRaw
        }, null, 2));
        const jsonResponse = { message: "OK" };
        console.log(jsonResponse);
        res.json(jsonResponse);
    });
    await app.listen(port, () => {
        console.log(`Example app listening on port ${port}`);
    });
}
createServer();
