export default {
    props: ['receiptId'],
    data() {
        return {
            receipt: null,
            userName: '',
            userSelections: {}
        }
    },
    methods: {
        async fetchReceipt() {
            try {
                const response = await axios.get(`/api/receipt/${this.receiptId}`)
                this.receipt = response.data
            } catch (error) {
                console.error('Error fetching receipt:', error)
            }
        },
        submitName() {
            if (this.userName.trim()) {
                this.fetchReceipt()
            }
        },
        toggleSelection(itemId) {
            this.userSelections[itemId] = !this.userSelections[itemId]
        },
        async submitSelections() {
            try {
                await axios.post(`/api/receipt/${this.receiptId}`, {
                    user: this.userName,
                    selections: this.userSelections
                })
                this.fetchReceipt()
            } catch (error) {
                console.error('Error submitting selections:', error)
            }
        }
    },
    mounted() {
        setInterval(this.fetchReceipt, 5000) // Fetch updates every 5 seconds
    },
    template: `
        <div v-if="!userName">
            <h2>Enter your name:</h2>
            <input v-model="userName" @keyup.enter="submitName">
            <button @click="submitName">Submit</button>
        </div>
        <div v-else-if="receipt">
            <h2>Receipt Items</h2>
            <table>
                <thead>
                    <tr>
                        <th>Select</th>
                        <th>Item</th>
                        <th>Price</th>
                        <th>Selected By</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="item in receipt.items" :key="item.id">
                        <td><input type="checkbox" :checked="userSelections[item.id]" @change="toggleSelection(item.id)"></td>
                        <td>{{ item.name }}</td>
                        <td>{{ item.price }}</td>
                        <td>{{ receipt.selections[item.id]?.join(', ') || '' }}</td>
                    </tr>
                </tbody>
            </table>
            <button @click="submitSelections">Submit Selections</button>
        </div>
    `
}