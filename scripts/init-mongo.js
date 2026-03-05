// This script runs automatically when MongoDB container starts
// It initializes the database with collections for chat history

db = db.getSiblingDB('netai_copilot');

// Create the chat_history collection with schema validation
db.createCollection('chat_history', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['timestamp', 'tenant_id', 'role', 'content'],
      properties: {
        _id: { bsonType: 'objectId' },
        timestamp: { bsonType: 'date' },
        tenant_id: { bsonType: 'string' },
        session_id: { bsonType: 'string' },
        role: { 
          enum: ['user', 'assistant'],
          description: 'Message sender (user or AI assistant)'
        },
        content: { bsonType: 'string' },
        metadata: {
          bsonType: 'object',
          properties: {
            agent_type: { bsonType: 'string' },
            model: { bsonType: 'string' },
            tokens_used: { bsonType: 'int' }
          }
        }
      }
    }
  }
});

// Create indexes for fast queries
db.chat_history.createIndex({ 'tenant_id': 1, 'session_id': 1, 'timestamp': -1 });
db.chat_history.createIndex({ 'session_id': 1 });
db.chat_history.createIndex({ 'timestamp': -1 });

print('✅ MongoDB initialized with chat_history collection');

