// ============================================================================
// MongoDB - cadastrais + dossies de emergencia (Camada 4, document store).
// Documentos aninhados e heterogeneos (variedade - R10); consistencia por
// documento (Cattell 2011). Executado pelo docker-entrypoint-initdb.d na 1a
// subida (o mongo:7 SUPORTA initdb.d para .js).
// Cria colecoes, indices e semeia cadastrais canonicos coerentes com o dominio.
// ============================================================================

const db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || "frota");

// --- Colecoes + validacao leve ---------------------------------------------
db.createCollection("veiculos");
db.createCollection("clientes");
db.createCollection("dossies");   // dossie regulatorio point-in-time (R8)

// --- Indices ----------------------------------------------------------------
db.veiculos.createIndex({ vehicle_id: 1 }, { unique: true });
db.veiculos.createIndex({ empresa: 1, categoria: 1 });
db.clientes.createIndex({ id_cliente: 1 }, { unique: true });
db.dossies.createIndex({ id_ocorrencia: 1 }, { unique: true });
db.dossies.createIndex({ vehicle_id: 1, event_ts: -1 });

// --- Seed de veiculos (coerente com fleetlib.domain: 6 empresas/patios) -----
const empresas = ["AutoRio Locadora", "MoveFrota", "VelozCar", "UnidasFrota", "Carioca Rent", "Litoral Autos"];
const categorias = ["Economico", "Intermediario", "SUV", "Executivo", "Utilitario"];
const patios = ["Galeao", "Santos Dumont", "Barra", "Copacabana", "Centro", "Niteroi"];
const modelos = {
  Economico: ["VW Gol", "Fiat Mobi"],
  Intermediario: ["Chevrolet Onix", "Hyundai HB20"],
  SUV: ["Jeep Compass", "VW T-Cross"],
  Executivo: ["Toyota Corolla", "Honda Civic"],
  Utilitario: ["Fiat Fiorino", "Renault Kangoo"],
};

const veiculos = [];
const N = 12; // alinhado ao FLEET_NUM_VEICULOS padrao
for (let i = 0; i < N; i++) {
  const cat = categorias[i % categorias.length];
  const emp = empresas[i % empresas.length];
  const mdl = modelos[cat][i % 2];
  veiculos.push({
    vehicle_id: "VEH-" + String(i + 1).padStart(3, "0"),
    placa: "AUT" + String(1000 + i),
    empresa: emp,
    categoria: cat,
    marca: mdl.split(" ")[0],
    modelo: mdl,
    mecanizacao: "Automatico",     // frota autonoma: sempre automatica
    autonoma: true,
    patio_base: patios[i % patios.length],
    firmware: { versao: "1.0.0", instalado_em: "2026-01-15" },
    sensores: [
      { id_sensor: "SEN-" + (i + 1) + "-GPS", tipo: "GPS", fabricante: "Garmin", unidade: "graus" },
      { id_sensor: "SEN-" + (i + 1) + "-BAT", tipo: "Bateria", fabricante: "BYD", unidade: "%" },
      { id_sensor: "SEN-" + (i + 1) + "-CAM", tipo: "Camera360", fabricante: "Mobileye", unidade: "frame" },
    ],
  });
}
db.veiculos.insertMany(veiculos);

// --- Seed de clientes -------------------------------------------------------
const cidades = [
  ["Rio de Janeiro", "RJ"], ["Niteroi", "RJ"], ["Sao Paulo", "SP"],
  ["Belo Horizonte", "MG"], ["Vitoria", "ES"], ["Campinas", "SP"],
];
const clientes = [];
for (let i = 0; i < 8; i++) {
  const c = cidades[i % cidades.length];
  clientes.push({
    id_cliente: "CLI-" + String(i + 1).padStart(3, "0"),
    nome: "Cliente " + (i + 1),
    cidade: c[0],
    estado: c[1],
    idade: 22 + (i * 7) % 45,
  });
}
db.clientes.insertMany(clientes);

print("MongoDB seed: " + db.veiculos.countDocuments() + " veiculos, " + db.clientes.countDocuments() + " clientes.");
