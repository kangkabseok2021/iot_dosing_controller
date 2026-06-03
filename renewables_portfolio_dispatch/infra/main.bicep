@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Name prefix for all resources')
param prefix string = 'renewdispatch'

@description('PostgreSQL admin password')
@secure()
param pgAdminPassword string

// ── PostgreSQL Flexible Server ────────────────────────────────────────────────
resource pgServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-03-01-preview' = {
  name: '${prefix}-pg'
  location: location
  sku: { name: 'Standard_D2s_v3', tier: 'GeneralPurpose' }
  properties: {
    administratorLogin: 'dispatch'
    administratorLoginPassword: pgAdminPassword
    version: '16'
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
  }
}

resource pgDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-03-01-preview' = {
  parent: pgServer
  name: 'dispatch'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

// ── Redis Cache ───────────────────────────────────────────────────────────────
resource redis 'Microsoft.Cache/Redis@2023-08-01' = {
  name: '${prefix}-redis'
  location: location
  properties: {
    sku: { name: 'Basic', family: 'C', capacity: 1 }
    enableNonSslPort: false
  }
}

// ── Storage Account (Fahrplan archive) ───────────────────────────────────────
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${replace(prefix, '-', '')}stor'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: { allowBlobPublicAccess: false, minimumTlsVersion: 'TLS1_2' }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'fahrplan-archive'
  properties: { publicAccess: 'None' }
}

// ── Container Apps Environment ────────────────────────────────────────────────
resource env 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${prefix}-env'
  location: location
  properties: {}
}

// ── Forecast API Container App ────────────────────────────────────────────────
resource forecastApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${prefix}-forecast'
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000 }
    }
    template: {
      containers: [
        {
          name: 'forecast-api'
          image: 'ghcr.io/kangkabseok2021/renewables-dispatch:latest'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'DATABASE_URL', value: 'postgresql+asyncpg://dispatch:${pgAdminPassword}@${pgServer.properties.fullyQualifiedDomainName}:5432/dispatch' }
            { name: 'REDIS_URL', value: 'rediss://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:6380/0' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

output forecastFqdn string = forecastApp.properties.configuration.ingress.fqdn
