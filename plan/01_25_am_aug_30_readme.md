# Plan Document

## File Information
- **Created by**: Saim
- **Created on**: August 30, 2024 at 01:25 AM
- **Purpose**: Unknown

## Plan Content

## 🎯 **API-Based Memory System Implementation Plan**

### **Key Requirements Finalized:**

1. **Last 5 Chats**: 5 user + 5 bot exchanges (10 total messages)
2. **Keep Current Prompt System**: Common prompts + agent-specific prompts
3. **Weight System**: Cart Info (100%) > Last 10 Messages (80%) > Important Features (60%) > Summary (40%)
4. **API-Based Context Extraction**: Use free Groq API for context understanding and summarization
5. **Receipt Text**: Keep as-is, enhance with LLM + cart info

### **Updated Phase 1: Dual-API Memory Infrastructure**

**Step 1: Extend Session Manager with Dual-API Memory System**
- Add important features tracking (accumulating key details)
- Implement last 10 messages tracking (5 user + 5 bot) with high weight
- Add cart state memory with highest priority
- Create feature importance scoring system
- Implement dual-API strategy: Primary API for responses, Enhanced API for context
- Preserve current prompt system structure

**Step 2: Create Dual-API Context Extractor**
- **API Key 1 (Enhanced)**: Extract context from last 10 messages, cart info, important features
- **API Key 2 (Primary)**: Generate responses based on agent-specific memory allocation
- Create structured memory extraction system
- Implement agent-specific memory distribution in controller
- Create feature extraction and importance scoring via Enhanced API
- Add preference and feature tracking through Enhanced API calls
- Implement rule-based analysis integration

**Step 3: Add Weighted Memory Context Builder**
- Create memory weight hierarchy: Cart Info (100%) > Last 10 Messages (80%) > Important Features (60%) > Summary (40%)
- Implement smart memory truncation based on weights
- Add cart state preservation with highest priority
- Create feature accumulation and compression algorithms
- Integrate with existing prompt system
- Implement dual-API memory context building strategy

### **Updated Phase 2: Controller Memory Integration**

**Step 4: Modify Controller with Agent-Specific Memory Distribution**
- Implement agent-specific memory allocation system
- **General Info Agent**: Summary + Last 10 messages + Rule base (prevent out-of-context responses)
- **Product Info Agent**: Summary + Last 10 messages + Important features + Database + Rule base + Cart info
- **Order Agent**: Cart state (1st priority) + Important features + Database (2nd priority) + Summary + Last 10 messages + Rule base
- Create feature-aware response generation
- Maintain current prompt system integration

**Step 5: Enhance Agent Context with Dual-API Memory**
- Pass weighted memory context to each agent type
- Implement cart state priority in all agent interactions
- Add feature memory sharing across agents
- Create memory validation with weight checking
- Preserve agent-specific prompt functionality
- Route complex context tasks to Enhanced API

**Step 6: Update Response Generation with Dual-API Weights**
- Modify prompt building to include weighted memory context
- Implement cart state as highest priority context
- Add feature memory to enhance personalization
- Create memory performance monitoring
- Maintain common + agent-specific prompt structure
- Implement smart API selection based on task complexity

### **Updated Phase 3: Dual-API Prompt Enhancement**

**Step 7: Update Prompt Builder with Dual-API Memory**
- Add weighted memory context sections to prompts
- Implement cart state as primary context
- Add feature memory for personalization
- Create memory-aware prompt optimization
- Preserve existing prompt structure and formatting
- Implement dual-API prompt routing strategy

**Step 8: Add Dual-API Memory Weight Instructions to Prompts**
- Include weight-based memory usage instructions
- Add cart state priority guidelines
- Implement feature memory usage rules
- Create memory-aware response formatting
- Maintain current prompt instructions
- Add API selection guidelines for different task types

**Step 9: Optimize Dual-API Token Usage with Weighted Truncation**
- Implement weight-based memory truncation
- Add token counting with weight consideration
- Create memory compression based on importance
- Add memory optimization algorithms
- Implement cost-effective API usage strategy

### **Updated Phase 4: Testing & Optimization**

**Step 10: Dual-API Memory System Testing**
- Test memory weight hierarchy effectiveness
- Validate cart state preservation across interactions
- Test feature memory accuracy and usage
- Create memory performance benchmarks
- Test prompt system integration
- Test dual-API routing effectiveness

**Step 11: Integration Testing with Dual-API Features**
- Test all agents with dual-API memory system
- Validate cart state priority across agent switches
- Test feature memory sharing and usage
- Create end-to-end weighted memory flow tests
- Verify prompt system functionality
- Test API selection accuracy for different tasks

**Step 12: Performance Optimization with Dual-API**
- Optimize dual-API usage for cost-effectiveness
- Implement memory caching with weight consideration
- Add memory usage monitoring with weight tracking
- Create memory performance alerts
- Monitor API cost distribution and optimization

## 📊 **Dual-API Weight System Implementation:**

### **Memory Weight Hierarchy:**
1. **Cart State & Info (100% weight)**: Always preserved, highest priority
2. **Last 10 Messages (80% weight)**: 5 user + 5 bot exchanges, high priority
3. **Important Features (60% weight)**: Accumulated key details, medium priority
4. **Conversation Summary (40% weight)**: Long-term preferences, lower priority

### **Dual-API Feature Accumulation Strategy:**
- **Growing Feature Set**: Accumulate important features throughout conversation
- **Importance Scoring**: Prioritize user preferences, key decisions, important details
- **Feature Compression**: Maintain feature quality while managing size
- **Preference Tracking**: Capture likes/dislikes, dietary restrictions, etc.
- **Enhanced API Context Extraction**: Use Enhanced API for complex context understanding
- **Primary API Responses**: Use Primary API for general responses and simple queries

### **Dual-API Usage Strategy (Clarified Flow):**

**API Key 1 (Enhanced) - Context Extraction:**
- Extract conversation summary from last 10 messages
- Extract cart info and state
- Extract important features (preferences, habits, patterns)
- Apply rule-based analysis
- Create structured memory context

**API Key 2 (Primary) - Response Generation:**
- Generate final response based on assigned memory context
- Use agent-specific memory allocation
- Respond to user's new query with full context

**Controller Memory Distribution:**
- **General Info Agent**: Summary + Last 10 messages + Rule base
- **Product Info Agent**: Summary + Last 10 messages + Important features + Database + Rule base + Cart info  
- **Order Agent**: Summary + Last 10 messages + Cart state (1st priority) + Important features + Database (2nd priority) + Rule base

### **Example Dual-API Enhanced Memory Context:**
```
CART_STATE (100% weight):
- Items: 2x Chocolate Cake, 1x Coffee
- Total: $45.00
- Customer: John, Phone: 555-1234
- Fulfillment: Pickup at Downtown branch

LAST_10_MESSAGES (80% weight):
- User: "I want to order a chocolate cake"
- Bot: "Great choice! How many would you like?"
- User: "2 please, and a coffee"
- Bot: "Added to cart. Pickup or delivery?"
- User: "Pickup at downtown"
- Bot: "Perfect! What's your name for the order?"
- User: "John"
- Bot: "Thanks John! What's your phone number?"
- User: "555-1234"
- Bot: "Great! Your order is ready for confirmation."

IMPORTANT_FEATURES (60% weight) - Enhanced API Generated:
- User prefers chocolate desserts
- User orders pickup frequently
- User likes coffee with desserts
- User prefers Downtown branch
- User orders for 2 people
- User prefers afternoon pickup
- User has no dietary restrictions
- User likes rich desserts
- User prefers local branches
- User orders weekly

CONVERSATION_SUMMARY (40% weight) - Enhanced API Generated:
- User: John, prefers chocolate desserts, orders pickup
- Previous orders: chocolate cakes, coffee
- Dietary preferences: none mentioned
- Branch preference: Downtown
```

## 🚀 **Implementation Priority:**

**Step 1** will focus on:
1. **Cart State Memory**: Highest priority preservation
2. **Last 10 Messages**: 5 user + 5 bot exchanges tracking
3. **Feature Accumulation**: Growing important features tracking
4. **Dual-API Context Extraction**: Smart API routing strategy
5. **Weight System**: Hierarchical memory management
6. **Performance**: Direct truncation and optimization
7. **Prompt System**: Preserve current common + agent-specific prompts

**Dual-API Integration Benefits:**
- ✅ **No Local Model Storage**: No 4-5GB model files
- ✅ **Always Latest**: Latest model capabilities via API
- ✅ **Cost Effective**: Free Groq API usage + optimized cost distribution
- ✅ **Scalable**: Easy to handle high traffic
- ✅ **Maintenance Free**: No model updates needed
- ✅ **Smart Routing**: Use best API for each task type
- ✅ **Performance**: Fast responses + smart context understanding

**Would you like me to proceed with implementing Step 1: Extend Session Manager with Dual-API Memory System?**

This will include:
- Enhanced session manager with feature accumulation
- Cart state preservation with highest priority
- Last 10 messages tracking (5 user + 5 bot) with high weight
- Important features tracking and scoring
- Dual-API context extraction and summarization
- Direct memory truncation for performance
- Memory weight calculation system
- Integration with existing prompt system
- Smart API routing based on task complexity

This foundation will enable all subsequent improvements while maintaining the performance, accuracy, and current prompt system you require, using the dual-API strategy for enhanced context understanding and cost optimization.


## Next Steps to Do After Above:

### **Immediate Next Step: Implement Dual-API Memory System**
- **Step 1**: Extend Session Manager with Dual-API Memory System
- **Step 2**: Create Dual-API Context Extractor (Primary + Enhanced APIs)
- **Step 3**: Add Weighted Memory Context Builder with Smart API Routing

### **Why Dual-API Approach is Best:**
- ✅ **No Local Model Storage**: No 4-5GB model files to manage
- ✅ **Always Latest**: Latest model capabilities via free APIs
- ✅ **Cost Effective**: Optimized cost distribution (70% cheap, 30% enhanced)
- ✅ **Scalable**: Easy to handle high traffic
- ✅ **Maintenance Free**: No model updates needed
- ✅ **Deployment Ready**: Works immediately after setup
- ✅ **Smart Routing**: Use best API for each task type
- ✅ **Performance**: Fast responses + smart context understanding

### **Implementation Order:**
1. **Session Manager Enhancement** (Memory infrastructure)
2. **Dual-API Context Extractor** (Smart API routing)
3. **Weight System Integration** (Memory prioritization)
4. **Controller Integration** (Agent memory injection)
5. **Testing & Optimization** (Performance validation)
6. **API Cost Optimization** (Usage monitoring and routing)
---
*This plan document was created by Saim on August 30, 2024 at 01:25 AM.*


