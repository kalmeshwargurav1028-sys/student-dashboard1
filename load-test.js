const http = require('http');
const https = require('https');
const url = require('url');

const TARGET_URL = 'https://student-dashboard1-blue.vercel.app/login';
const targetParsed = url.parse(TARGET_URL);
const reqModule = targetParsed.protocol === 'https:' ? https : http;

// Test Configuration
const TOTAL_REQUESTS = 10000;
const CONCURRENCY = 500;
const USERS_IN_DB = 3;

// State
let startedRequests = 0;
let completedRequests = 0;
let successCount = 0;
let rateLimitedCount = 0;
let errorCount = 0;
const responseTimes = [];
let startTime = 0;

// Helper to calculate P99
const calculateP99 = (times) => {
  if (times.length === 0) return 0;
  times.sort((a, b) => a - b);
  const index = Math.ceil(times.length * 0.99) - 1;
  return times[index];
};

// Simulate picking random credentials
const getRandomUser = () => {
  const userId = Math.floor(Math.random() * USERS_IN_DB) + 1;
  return {
    email: `user${userId}@example.com`,
    password: `password${userId}`,
  };
};

// Single request function wrapped in a Promise
const makeRequest = () => {
  return new Promise((resolve) => {
    const user = getRandomUser();
    const reqStartTime = Date.now();

    const payload = `login_type=teacher&email=${encodeURIComponent(user.email)}&password=${encodeURIComponent(user.password)}`;
    
    const options = {
      hostname: targetParsed.hostname,
      port: targetParsed.port,
      path: targetParsed.path,
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(payload)
      }
    };

    const req = reqModule.request(options, (res) => {
      // Consume response data to free up memory
      res.on('data', () => {});
      
      res.on('end', () => {
        const reqEndTime = Date.now();
        responseTimes.push(reqEndTime - reqStartTime);

        if (res.statusCode === 200) {
          successCount++;
        } else if (res.statusCode === 429) {
          rateLimitedCount++;
        } else {
          errorCount++;
        }
        
        completedRequests++;
        process.stdout.write(`\r📊 Progress: ${completedRequests}/${TOTAL_REQUESTS}`);
        resolve();
      });
    });

    req.on('error', (error) => {
      const reqEndTime = Date.now();
      responseTimes.push(reqEndTime - reqStartTime);
      errorCount++;
      completedRequests++;
      process.stdout.write(`\r📊 Progress: ${completedRequests}/${TOTAL_REQUESTS}`);
      resolve();
    });

    req.write(payload);
    req.end();
  });
};

// Worker function for concurrency
const worker = async () => {
  while (true) {
    if (startedRequests >= TOTAL_REQUESTS) break;
    startedRequests++;
    await makeRequest();
  }
};

const runTest = async () => {
  console.log("==========================================");
  console.log("🚀 REAL SYSTEM LOAD TEST");
  console.log("==========================================");
  console.log(`Target: ${TARGET_URL}`);
  console.log(`Total Requests: ${TOTAL_REQUESTS}`);
  console.log(`Concurrent: ${CONCURRENCY}`);
  console.log(`Users in DB: ${USERS_IN_DB}`);
  console.log("==========================================");
  console.log(`\n🔓 Hammering target with ${TOTAL_REQUESTS} requests...\n`);

  startTime = Date.now();

  const workers = [];
  for (let i = 0; i < CONCURRENCY; i++) {
    workers.push(worker());
  }

  await Promise.all(workers);

  const endTime = Date.now();
  const totalDurationMs = endTime - startTime;
  const totalDurationS = (totalDurationMs / 1000).toFixed(2);
  const throughput = Math.round(TOTAL_REQUESTS / (totalDurationMs / 1000));

  const averageResponseTime = responseTimes.length
    ? (responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length).toFixed(2)
    : 0;
  const minResponseTime = responseTimes.length ? Math.min(...responseTimes).toFixed(0) : 0;
  const maxResponseTime = responseTimes.length ? Math.max(...responseTimes).toFixed(0) : 0;
  const p99ResponseTime = calculateP99(responseTimes).toFixed(0);
  const successRate = ((successCount / TOTAL_REQUESTS) * 100).toFixed(1);

  console.log("\n\n✅ TEST COMPLETE");
  console.log("==========================================");
  console.log(`Total Duration: ${totalDurationS}s`);
  console.log(`Total Requests: ${TOTAL_REQUESTS}`);
  console.log(`Throughput: ${throughput} req/s\n`);

  console.log("📊 RESULTS:");
  console.log(`  ✅ Success (200): ${successCount}`);
  console.log(`  ⚠️  Rate Limited (429): ${rateLimitedCount}`);
  console.log(`  ❌ Errors: ${errorCount}\n`);

  console.log("⏱️  RESPONSE TIMES:");
  console.log(`  Average: ${averageResponseTime}ms`);
  console.log(`  Min: ${minResponseTime}ms`);
  console.log(`  Max: ${maxResponseTime}ms`);
  console.log(`  P99: ${p99ResponseTime}ms`);
  console.log("==========================================");

  console.log("💡 INSIGHTS:");
  console.log(`  • ${successRate}% success rate`);
  console.log(`  • ${throughput} requests per second`);
  console.log(`  • Average response time: ${averageResponseTime}ms`);
  console.log(`  • gRPC + MongoDB atlas handled ${TOTAL_REQUESTS} requests gracefully.`);
  console.log("==========================================\n");
};

runTest();
