// ── API response types ──

export interface Character {
  name: string
  isMain: boolean
  faction?: string
  role_tags: string[]
  personality_tags: string[]
  appearance: string
  relationship: string[]
  goal: string
  secret: string
  background: string
  special_ability: string
  notes?: string
  trust_pct?: number   // 实际信任度 0-100，来自 memory.json（NPC 页面展示用）
}

export interface WorldGenRequest {
  keywords: string
}

export interface WorldGenResponse {
  title?: string
  world?: string
  genre?: string[]
  scene?: string
  main_goal?: string
  characters?: Character[]
  rel_stages?: string[]
  rel_affection?: number
  stats?: StatDimension[]
  factions?: FactionGenItem[]
  artifacts?: ArtifactGenItem[]
  characterRelations?: Record<string, CharacterRelation>
}

export interface FactionGenItem {
  name: string
  type: string
  description: string
  goals: string[]
  resources: string[]
  controlledTerritories: string[]
  subordinateOrganizations: string[]
  keyAssets: string[]
  power: { military: number; economic: number; political: number; technology: number }
  influence: number
  relation_to_player: string
  leader: string
}

export interface ArtifactGenItem {
  name: string
  type: string
  description: string
  ownerType: string
  ownerId: string
  importance: number
  abilities: string[]
  tags: string[]
}

export interface StatDimension {
  key: string
  label: string
  max: number
}

export interface CharacterRelation {
  relationshipType: string
  affection: number
  trust: number
  respect: number
  dependence: number
  hostility: number
  attraction: number
  tags: string[]
}

export interface FieldGenRequest {
  field: string
  title?: string
  world?: string
  genre?: string
  context?: string
  char_role?: string
  char_name?: string
}

export interface FieldGenResponse {
  story?: string
  title?: string
  name?: string
  main_goal?: string
  genre?: string[]
  rel_stages?: string[]
  rel_affection?: number
  role_tags?: string[]
  personality_tags?: string[]
  appearance?: string
  relationship?: string[]
  goal?: string
  secret?: string
  isMain?: boolean
  faction?: string
  relationshipType?: string
  affection?: number
  trust?: number
  respect?: number
  dependence?: number
  hostility?: number
  attraction?: number
  tags?: string[]
  error?: string
}

export interface GameState {
  scene: string
  status: 'SETUP' | 'BUILD' | 'TENSION' | 'CLIMAX' | 'COOLDOWN'
  turn: number
  characters: Record<string, StateCharacter>
  factions?: Record<string, unknown>[]
  history: unknown[]
  force_event_pending: boolean
  chapter: number
}

export interface StateCharacter {
  name: string
  role: string
  level: string
  relation: string
  note: string
}

export interface GameTurnResponse {
  story: string
  state: GameState
  options: string[]
  error?: string
}

export interface CustomRules {
  stats: StatDimension[]
  stages: string[]
}

export interface RelationshipSystem {
  stages: string[]
  affection: number
}

export interface StoryFormData {
  title: string
  world: string
  genre: string[]
  scene: string
  main_goal: string
  characters: Character[]
  custom_rules?: CustomRules
  rel_system: RelationshipSystem
}
